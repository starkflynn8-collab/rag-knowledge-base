from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any

import httpx
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough, RunnableWithMessageHistory

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config_data as config
from citation import format_citation, format_document_block, resolve_chunk_id
from corpus_cleaner import infer_doc_type, iter_supported_files, load_html, normalize_source
from document_loader import DocumentLoaderService
from file_history_store import get_history
from knowledge_base import KnowledgeBaseService
from rag import RagService


def file_md5(file_path: Path) -> str:
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)
    return md5.hexdigest()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def parse_chunk_count(message: str) -> int | None:
    match = re.search(r"共生成\s+(\d+)\s+个文本块", message or "")
    if match:
        return int(match.group(1))
    return None



def display_source_name(source: Any) -> str:
    name = PureWindowsPath(str(source or "未知来源").replace("/", "\\")).name
    suffix = PureWindowsPath(name).suffix
    if suffix:
        return name[: -len(suffix)]
    return name


def display_doc_type(source: Any, metadata_type: Any = None) -> str:
    suffix = PureWindowsPath(str(source or "").replace("/", "\\")).suffix.lower().lstrip(".")
    if suffix:
        return suffix
    value = str(metadata_type or "unknown").strip().lower()
    return value or "unknown"
def normalize_page(value: Any) -> str:
    if value in (None, "", "unknown"):
        return "unknown"
    return str(value)


def normalize_document_type(source: Any, current_type: Any = None) -> str:
    """按文件后缀归一化类型，兼容历史 metadata 中的 unknown/manual。"""
    source_text = str(source or "")
    suffix = Path(source_text).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".html", ".htm"}:
        return "html"
    if current_type not in (None, "", "unknown", "manual"):
        return str(current_type)
    return str(current_type or "unknown")


def normalize_html_source_path(source: Any) -> str:
    normalized = normalize_source(str(source or ""))
    if normalized.lower().startswith("html\\"):
        return normalized[6:]
    return normalized


class AppServices:
    def __init__(self) -> None:
        self.loader = DocumentLoaderService()
        self.kb = KnowledgeBaseService()
        self.rag = RagService()
        self.answer_chain = self._build_answer_chain()

    def switch_model_mode(self, mode: str) -> dict[str, Any]:
        """切换当前进程的生成模型和 rerank 模型，不重建 embedding 或 Chroma。"""
        requested = config.model_profile(mode)
        if not requested["chat_api_key_configured"] or not requested["rerank_api_key_configured"]:
            provider = "阿里百炼" if requested["mode"] == "dashscope" else "Cloudflare"
            raise ValueError(f"{provider} API 凭据未配置，无法切换")

        old_mode = config.model_mode
        config.set_model_mode(mode)
        try:
            self.rag.rebuild_chat_model()
            self.answer_chain = self._build_answer_chain()
        except Exception:
            config.set_model_mode(old_mode)
            self.rag.rebuild_chat_model()
            self.answer_chain = self._build_answer_chain()
            raise
        return self.model_status()

    @staticmethod
    def model_status() -> dict[str, Any]:
        profile = config.model_profile()
        return {
            "mode": profile["mode"],
            "llm": {
                "provider": profile["chat_provider"],
                "model": profile["chat_model"],
                "available": profile["chat_api_key_configured"],
            },
            "rerank": {
                "provider": profile["rerank_provider"],
                "model": profile["rerank_model"],
                "available": profile["rerank_api_key_configured"],
            },
        }

    @staticmethod
    def is_small_talk(question: str) -> bool:
        """识别不需要知识库检索的简单问候，避免被拒答阈值误判。"""
        normalized = re.sub(r"[\s，。！？、,.!?；;：:~～]+", "", question or "").lower()
        return bool(
            re.fullmatch(
                r"(你好|您好|嗨|嗨嗨|哈喽|hello|hi|hey|早上好|上午好|中午好|下午好|晚上好|晚安|谢谢|多谢|再见|拜拜)(啊|呀|喽)?",
                normalized,
            )
        )

    @staticmethod
    def small_talk_response(question: str) -> str:
        normalized = re.sub(r"[\s，。！？、,.!?；;：:~～]+", "", question or "").lower()
        if normalized in {"谢谢", "多谢"}:
            return "不客气！如果有 ZRDDS 技术问题，随时可以继续问我。"
        if normalized in {"再见", "拜拜"}:
            return "再见！需要查询 ZRDDS 文档时随时回来。"
        return "你好！我是 DDS 技术文档问答助手。你可以直接问我 ZRDDS 的安装、配置、使用或故障排查问题。"

    def _build_answer_chain(self):
        def normalize_prompt_input(value: dict[str, Any]) -> dict[str, Any]:
            return {
                "input": value["input"],
                "context": value.get("context", ""),
                "history": value.get("history", []),
            }

        base_chain = (
            RunnablePassthrough()
            | RunnableLambda(normalize_prompt_input)
            | self.rag.prompt_template
            | self.rag.chat_model
            | StrOutputParser()
        )

        return RunnableWithMessageHistory(
            base_chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    def _all_documents(self) -> list[Document]:
        data = self.kb.chroma.get()
        documents = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []
        result: list[Document] = []
        for i, page_content in enumerate(documents):
            metadata = {}
            if i < len(metadatas):
                metadata = metadatas[i] or {}
            result.append(Document(page_content=page_content, metadata=metadata))
        return result

    def _group_documents(self) -> list[dict[str, Any]]:
        all_docs = self._all_documents()
        grouped: dict[str, list[Document]] = defaultdict(list)
        for doc in all_docs:
            source = doc.metadata.get("source", "未知来源")
            grouped[str(source)].append(doc)

        items: list[dict[str, Any]] = []
        for source, docs in grouped.items():
            first = docs[0].metadata if docs else {}
            page_values = [
                normalize_page(doc.metadata.get("page"))
                for doc in docs
                if normalize_page(doc.metadata.get("page")) != "unknown"
            ]
            page_count = len(set(page_values)) if page_values else None
            items.append(
                {
                    "source": display_source_name(source),
                    "source_path": source,
                    "doc_type": display_doc_type(source, first.get("doc_type", "unknown")),
                    "version": first.get("version", "unknown"),
                    "chunk_count": len(docs),
                    "page_count": page_count,
                    "create_time": first.get("create_time"),
                    "operator": first.get("operator"),
                }
            )
        items.sort(
            key=lambda x: (
                0 if x["doc_type"] == "pdf" else 1,
                str(x["source"]).lower(),
            )
        )
        return items

    def health(self) -> dict[str, Any]:
        embedding_available = False
        try:
            resp = httpx.get(f"{config.ollama_base_url}/api/tags", timeout=2.5)
            embedding_available = resp.status_code == 200
        except Exception:
            embedding_available = False

        docs = self._all_documents()
        return {
            "status": "ok",
            "app": "DDSRag v2",
            "api_version": "1.0",
            "embedding": {
                "provider": config.embedding_provider,
                "model": config.embedding_model_name,
                "base_url": config.ollama_base_url,
                "available": embedding_available,
            },
            "llm": {
                "provider": config.model_profile()["chat_provider"],
                "model": config.model_profile()["chat_model"],
                "available": config.model_profile()["chat_api_key_configured"],
            },
            "rerank": {
                "provider": config.model_profile()["rerank_provider"],
                "model": config.model_profile()["rerank_model"],
                "available": config.model_profile()["rerank_api_key_configured"],
            },
            "model_mode": config.model_mode,
            "retrieval": {
                "default_mode": config.default_retrieval_mode,
                "vector_top_k": config.vector_top_k,
                "bm25_top_k": config.bm25_top_k,
                "rrf_top_k": config.rrf_top_k,
                "rerank_top_k": config.rerank_top_k,
            },
            "knowledge_base": {
                "collection": config.collection_name,
                "persist_directory": config.persist_directory,
                "document_count": len({doc.metadata.get("source", "") for doc in docs}),
                "chunk_count": len(docs),
            },
        }

    def config_payload(self) -> dict[str, Any]:
        return {
            "embedding_provider": config.embedding_provider,
            "embedding_model_name": config.embedding_model_name,
            "ollama_base_url": config.ollama_base_url,
            "chat_model_name": config.chat_model_name,
            "rerank_model_name": config.rerank_model_name,
            "model_mode": config.model_mode,
            "model_options": {
                "cloudflare": {
                    "llm_provider": "cloudflare",
                    "llm_model": config.cloudflare_chat_model_name,
                    "rerank_provider": "cloudflare",
                    "rerank_model": config.cloudflare_rerank_model_name,
                    "configured": bool(config.CLOUDFLARE_API_TOKEN),
                },
                "dashscope": {
                    "llm_provider": "dashscope",
                    "llm_model": config.dashscope_chat_model_name,
                    "rerank_provider": "dashscope",
                    "rerank_model": config.dashscope_rerank_model_name,
                    "configured": bool(config.DASHSCOPE_API_KEY),
                },
            },
            "default_retrieval_mode": config.default_retrieval_mode,
            "vector_top_k": config.vector_top_k,
            "bm25_top_k": config.bm25_top_k,
            "rrf_top_k": config.rrf_top_k,
            "rerank_top_k": config.rerank_top_k,
            "embedding_batch_size": config.embedding_batch_size,
        }

    def list_documents(self, doc_type: str | None, keyword: str | None, page: int, page_size: int) -> dict[str, Any]:
        items = self._group_documents()

        if doc_type:
            items = [item for item in items if str(item.get("doc_type", "")).lower() == doc_type.lower()]

        if keyword:
            lower = keyword.lower()
            items = [item for item in items if lower in str(item.get("source", "")).lower()]

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items[start:end],
        }

    def document_stats(self) -> dict[str, Any]:
        items = self._group_documents()
        by_doc_type = Counter()
        by_version = Counter()
        for item in items:
            by_doc_type[str(item.get("doc_type", "unknown"))] += 1
            by_version[str(item.get("version", "unknown"))] += 1
        all_docs = self._all_documents()
        return {
            "source_count": len(items),
            "chunk_count": len(all_docs),
            "by_doc_type": dict(sorted(by_doc_type.items())),
            "by_version": dict(sorted(by_version.items())),
        }

    def document_preview(self, source_path: str, limit: int = 80) -> dict[str, Any]:
        requested_source = normalize_source(Path(source_path).as_posix())
        documents = [
            doc
            for doc in self._all_documents()
            if normalize_source(str(doc.metadata.get("source", ""))) == requested_source
        ]
        if not documents:
            raise FileNotFoundError(f"知识库中没有找到文档：{source_path}")

        chunks = []
        for doc in documents[:limit]:
            metadata = doc.metadata or {}
            chunks.append(
                {
                    "chunk_id": resolve_chunk_id(metadata, doc.page_content),
                    "page": normalize_page(metadata.get("page")),
                    "text": doc.page_content,
                }
            )

        first_metadata = documents[0].metadata or {}
        return {
            "source": first_metadata.get("source", requested_source),
            "source_path": requested_source,
            "doc_type": normalize_document_type(
                first_metadata.get("source", requested_source),
                first_metadata.get("doc_type"),
            ),
            "version": first_metadata.get("version", "unknown"),
            "chunk_count": len(documents),
            "preview_chunk_count": len(chunks),
            "truncated": len(documents) > limit,
            "chunks": chunks,
        }

    def html_source_file(self, source_path: str) -> Path:
        """解析 HTML 原始文件，并限制访问范围在配置的 HTML 根目录内。"""
        root = Path(config.html_source_root).expanduser().resolve()
        relative = Path(normalize_html_source_path(source_path).replace("\\", "/"))
        candidate = (root / relative).resolve()
        if root != candidate and root not in candidate.parents:
            raise FileNotFoundError("HTML 路径不在允许的文档目录内")
        if candidate.suffix.lower() not in {".html", ".htm"} or not candidate.is_file():
            raise FileNotFoundError(f"原始 HTML 不存在：{source_path}")
        return candidate

    #引用粒度分级方法
    def _citation_granularity(self, score: float) -> str:
        if score >= config.citation_granularity_thresholds["fine"]:
            return "fine"
        elif score >= config.citation_granularity_thresholds["medium"]:
            return "medium"
        else:
            return "coarse"

    def _format_documents(
        self,
        documents: list[Document],
        include_text: bool = True,
        scores: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        raw = []
        for index, doc in enumerate(documents, start=1):
            metadata = doc.metadata or {}
            score = scores[index - 1] if scores and index - 1 < len(scores) else None
            granularity = self._citation_granularity(score) if score is not None else "coarse"

            chunk_id = resolve_chunk_id(metadata, doc.page_content)
            citation = format_citation(metadata, doc.page_content)
            if granularity == "medium":
                source = metadata.get("source", "未知来源")
                page = normalize_page(metadata.get("page"))
                citation = f"{source} | p.{page}" if page != "unknown" else source

            item = {
                "index": index,
                "source": metadata.get("source", "未知来源"),
                "doc_type": normalize_document_type(
                    metadata.get("source"),
                    metadata.get("doc_type"),
                ),
                "version": metadata.get("version", "unknown"),
                "page": normalize_page(metadata.get("page")),
                "chunk_id": chunk_id,
                "source_chunk_id": metadata.get("source_chunk_id"),
                "citation": citation,
                "score": score,
                "granularity": granularity,
                "text": doc.page_content if include_text else None,
                "snippet": doc.page_content[:240] if granularity != "coarse" else None,
            }
            raw.append(item)

        seen_sources = set()
        result = []
        for item in raw:
            if item["granularity"] == "coarse":
                if item["source"] in seen_sources:
                    continue
                seen_sources.add(item["source"])
            result.append(item)
        return result

    def _retrieve_raw(
        self,
        query: str,
        retrieval_mode: str,
        k: int,
        rerank: bool = True,
    ) -> tuple[list[Document], list[float]]:
        vector_service = self.rag.vector_service
        limit = max(1, k)

        if retrieval_mode == "vector":
            docs = vector_service.vector_store.similarity_search(query, k=limit)
            if rerank:
                docs = vector_service.rerank(query, docs, top_n=limit)
            return docs[:limit]

        vector_docs = vector_service.vector_store.similarity_search(query, k=max(limit, config.vector_top_k))
        bm25_retriever = vector_service.get_bm25_retriever()
        if bm25_retriever is None:
            docs = vector_docs
            if rerank:
                docs = vector_service.rerank(query, docs, top_n=limit)
            return docs[:limit]

        old_k = bm25_retriever.k
        bm25_retriever.k = max(limit, config.bm25_top_k)
        try:
            bm25_docs = bm25_retriever.invoke(query)
        finally:
            bm25_retriever.k = old_k

        fused_docs = vector_service._rrf_fusion(vector_docs, bm25_docs, k=config.rrf_const, top_k=limit)
        if rerank:
            fused_docs = vector_service.rerank(query, fused_docs, top_n=limit)
        return fused_docs[:limit]

    def document_preview(self, source_path: str, max_chunks: int = 80) -> dict[str, Any]:
        source_key = str(source_path or "")
        chunks = [doc for doc in self._all_documents() if str(doc.metadata.get("source", "")) == source_key]
        chunks.sort(key=lambda doc: safe_int(doc.metadata.get("chunk_id"), 0))
        limited = chunks[: max(1, max_chunks)]
        return {
            "source": display_source_name(source_key),
            "source_path": source_key,
            "doc_type": display_doc_type(source_key, chunks[0].metadata.get("doc_type") if chunks else None),
            "chunk_count": len(chunks),
            "preview_chunk_count": len(limited),
            "truncated": len(limited) < len(chunks),
            "chunks": [
                {
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "page": normalize_page(doc.metadata.get("page")),
                    "text": doc.page_content,
                }
                for doc in limited
            ],
        }
    def retrieve(self, query: str, retrieval_mode: str, k: int, rerank: bool = True) -> dict[str, Any]:
        documents, scores = self._retrieve_raw(query=query, retrieval_mode=retrieval_mode, k=k, rerank=rerank)
        return {
            "query": query,
            "retrieval_mode": retrieval_mode,
            "documents": self._format_documents(documents, include_text=True),
            "document_count": len(documents),
        }

    def build_context(self, documents: list[Document]) -> str:
        if not documents:
            return "无相关资料"
        parts = []
        for index, doc in enumerate(documents, start=1):
            parts.append(format_document_block(index, doc))
        return "\n\n".join(parts)

    def answer(
        self,
        question: str,
        session_id: str,
        retrieval_mode: str,
        top_k: int,
        return_context: bool = True,
    ) -> dict[str, Any]:
        start = datetime.now()

        if self.is_small_talk(question):
            return {
                "answer": self.small_talk_response(question),
                "refused": False,
                "refusal_score": None,
                "session_id": session_id,
                "retrieval_mode": "none",
                "citations": [],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
                "latency_ms": int((datetime.now() - start).total_seconds() * 1000),
            }

        docs, scores = self._retrieve_raw(question, retrieval_mode, top_k, rerank=True)

        #比较最高分与拒绝阈值，显式拒绝无法回答的问题
        top_score = scores[0] if scores else 0.0
        if top_score < config.refusal_score_threshold:
            latency_ms = int((datetime.now() - start).total_seconds() * 1000)
            return {
                "answer": "抱歉，当前知识库中没有足够相关的资料来回答该问题。",
                "refused": True,
                "refusal_score": top_score,
                "session_id": session_id,
                "retrieval_mode": retrieval_mode,
                "citations": [],
                "usage": {
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                },
                "latency_ms": latency_ms,
            }

        context = self.build_context(docs) if return_context else self.build_context(docs)
        answer_text = self.answer_chain.invoke(
            {"input": question, "context": context},
            {"configurable": {"session_id": session_id}},
        )
        latency_ms = int((datetime.now() - start).total_seconds() * 1000)
        return {
            "answer": answer_text,
            "refused": False,
            "session_id": session_id,
            "retrieval_mode": retrieval_mode,
            "citations": self._format_documents(docs, include_text=return_context),
            "citation_count": len(docs),
            "usage": {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            },
            "latency_ms": latency_ms,
        }

    def stream_answer(
        self,
        question: str,
        session_id: str,
        retrieval_mode: str,
        top_k: int,
        return_context: bool = True,
    ):
        if self.is_small_talk(question):
            return [], [], self.small_talk_response(question)

        docs, scores = self._retrieve_raw(question, retrieval_mode, top_k, rerank=True)

        top_score = scores[0] if scores else 0.0
        if top_score < config.refusal_score_threshold:
            refusal_msg = "抱歉，当前知识库中没有足够相关的资料来回答该问题。"
            return docs, scores, refusal_msg

        context = self.build_context(docs) if return_context else self.build_context(docs)
        answer = self.answer_chain.invoke(
            {"input": question, "context": context},
            {"configurable": {"session_id": session_id}},
        )
        return docs, scores, answer

    def list_sessions(self) -> dict[str, Any]:
        history_dir = Path("./chat_history")
        items: list[dict[str, Any]] = []
        if not history_dir.exists():
            return {"items": []}

        for path in history_dir.iterdir():
            if not path.is_file():
                continue
            session_id = path.name
            history = get_history(session_id)
            messages = history.messages
            first_user = next((msg.content for msg in messages if isinstance(msg, HumanMessage)), "")
            last_message = messages[-1].content if messages else ""
            stat = path.stat()
            items.append(
                {
                    "session_id": session_id,
                    "title": str(first_user or session_id)[:40],
                    "message_count": len(messages),
                    "last_message": str(last_message)[:120],
                    "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )

        items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return {"items": items}

    def get_session_history(self, session_id: str) -> dict[str, Any]:
        history = get_history(session_id)
        messages = []
        for msg in history.messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            else:
                role = getattr(msg, "type", "assistant")
            messages.append({"role": role, "content": str(msg.content)})
        return {"session_id": session_id, "messages": messages}
    def upload_file(self, file_path: Path, original_name: str, operator: str = "小虎") -> dict[str, Any]:
        documents = self.loader.load(str(file_path))
        result = self.kb.upload_documents(
            documents=documents,
            filename=original_name,
            file_md5=file_md5(file_path),
            operator=operator,
        )
        return {
            "filename": original_name,
            "status": "success" if result.startswith("[成功]") else "skipped" if result.startswith("[跳过]") else "failed",
            "message": result,
            "chunk_count": parse_chunk_count(result),
            "parsed_documents": len(documents),
        }

    def batch_ingest(self, path: str, include_noise_html: bool = False, dry_run: bool = False, operator: str = "小虎") -> dict[str, Any]:
        input_path = Path(path).expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"路径不存在：{input_path}")

        if input_path.is_file():
            candidates = [(input_path, Path(input_path.name), "keep")]
        else:
            candidates = list(iter_supported_files(input_path, include_noise_html))

        kept_files = [item for item in candidates if item[2] == "keep"]
        skipped_noise = [item for item in candidates if item[2] == "noise-html"]

        payload = {
            "path": str(input_path),
            "dry_run": dry_run,
            "include_noise_html": include_noise_html,
            "total_files": len(candidates),
            "kept_files": len(kept_files),
            "skipped_noise_html": len(skipped_noise),
            "success_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "results": [],
            "failures": [],
        }

        if dry_run:
            payload["results"] = [
                {
                    "source": normalize_source(relative_path),
                    "status": "keep",
                    "message": "dry-run",
                    "chunk_count": None,
                    "skipped_reason": None,
                }
                for _, relative_path, _ in kept_files
            ]
            return payload

        for file_path, relative_path, _ in kept_files:
            source = normalize_source(relative_path)
            try:
                if file_path.suffix.lower() in {".html", ".htm"}:
                    documents = load_html(file_path)
                else:
                    documents = self.loader.load(str(file_path))

                for doc in documents:
                    doc.metadata["doc_type"] = infer_doc_type(relative_path)

                result = self.kb.upload_documents(
                    documents=documents,
                    filename=source,
                    file_md5=file_md5(file_path),
                    operator=operator,
                )
                status = "skipped" if result.startswith("[跳过]") else "success"
                if status == "skipped":
                    payload["skipped_count"] += 1
                else:
                    payload["success_count"] += 1
                payload["results"].append(
                    {
                        "source": source,
                        "status": status,
                        "message": result,
                        "chunk_count": parse_chunk_count(result),
                        "skipped_reason": "duplicate-md5" if status == "skipped" else None,
                    }
                )
            except Exception as e:
                payload["failed_count"] += 1
                payload["results"].append(
                    {
                        "source": source,
                        "status": "failed",
                        "message": str(e),
                        "chunk_count": None,
                        "skipped_reason": None,
                    }
                )
                payload["failures"].append(
                    {
                        "source": source,
                        "error": str(e),
                    }
                )

        return payload

    def clear_history(self, session_id: str) -> None:
        history = get_history(session_id)
        history.clear()






