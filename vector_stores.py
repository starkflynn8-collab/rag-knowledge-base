"""
检索基础设施：

1. Chroma 向量检索
2. BM25 关键词检索
3. RRF 混合检索
4. Cloudflare / DashScope Reranker 重排序
"""

import hashlib
import re
import json
import urllib.request

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

import config_data as config


def tokenize_for_bm25(text):
    """中文按单字、英文数字/API 符号按词切分，适配技术文档检索。"""
    return re.findall(
        r"[a-zA-Z_][a-zA-Z0-9_:~]*|[0-9]+|[\u4e00-\u9fff]",
        text.lower(),
    )


class VectorStoreService(object):

    def __init__(self, embedding):

        self.embedding = embedding

        # =========================
        # 1. Chroma 向量数据库
        # =========================

        self.vector_store = Chroma(
            collection_name=config.collection_name,
            embedding_function=self.embedding,
            persist_directory=config.persist_directory,
        )

        # =========================
        # 2. 构建 BM25 检索器
        # =========================

        self.bm25_retriever = self._build_bm25_retriever()

# =========================================================
# 获取向量检索器
# =========================================================

    def get_vector_retriever(self):
        return self.vector_store.as_retriever(
            search_kwargs={"k": config.vector_top_k}
        )

# =========================================================
# 从 Chroma 获取全部 Document，供BM25检索
# =========================================================

    def _get_all_documents(self):

        data = self.vector_store.get()

        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        result = []

        for i, page_content in enumerate(documents):

            metadata = {}

            if i < len(metadatas):
                metadata = metadatas[i] or {}

            result.append(
                Document(
                    page_content=page_content,
                    metadata=metadata,
                )
            )

        return result


# =========================================================
# 构建 BM25 检索器
# =========================================================

    def _build_bm25_retriever(self):

        documents = self._get_all_documents()

        if not documents:
            return None

        retriever = BM25Retriever.from_documents(
            documents,
            preprocess_func=tokenize_for_bm25
        )

        retriever.k = config.bm25_top_k

        return retriever

# =========================================================
# 获取 BM25 检索器
# =========================================================

    def get_bm25_retriever(self):

        return self.bm25_retriever

# =========================================================
# 根据 Document 内容生成唯一临时ID ，供RRF识别去重
# =========================================================

    def _get_document_id(self, doc):

        source = doc.metadata.get("source", "")
        chunk_id = doc.metadata.get("chunk_id")

        if chunk_id not in (None, "", "unknown"):
            return f"{source}#{chunk_id}"

        source_chunk_id = doc.metadata.get("source_chunk_id")

        if source_chunk_id not in (None, "", "unknown"):
            return str(source_chunk_id)

        content = doc.page_content

        raw = source + content  # 使用source + page_content 生成MD5唯一标识

        return hashlib.md5(
            raw.encode("utf-8")
        ).hexdigest()

# =========================================================
# 使用 RRF 对向量检索和 BM25 检索结果进行融合
# =========================================================
    def _rrf_fusion(self, vector_docs, bm25_docs, k=None):

        if k is None:
            k = config.rrf_const

        scores = {}
        documents = {}

        # =========================
        # 处理向量检索结果，Vector 排名
        # =========================

        for rank, doc in enumerate(vector_docs, start=1):
            doc_id = self._get_document_id(doc)

            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank) # RRF公式

            documents[doc_id] = doc

        # =========================
        # 处理 BM25 检索结果，BM25 排名
        # =========================

        for rank, doc in enumerate(bm25_docs, start=1):
            doc_id = self._get_document_id(doc)

            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)

            documents[doc_id] = doc

        # =========================
        # 根据 RRF 分数排序
        # =========================

        sorted_ids = sorted(
            scores,
            key=scores.get,
            reverse=True
        )
        # -------------------------
        # 返回 Top K
        # -------------------------
        results = []

        for doc_id in sorted_ids[ :config.rrf_top_k]:
            results.append(
                documents[doc_id]
            )

        return results

# =========================================================
# Reranker 重排
# =========================================================
    def rerank(self, query, documents) -> tuple[list, list[float]]:
        #重排方法签名修改，额外返回各chunk的重排得分，用于实现动态引用粒度以及与拒绝阈值比较
        if not documents:
            return [], []

        # 提取文本
        document_texts = [
            doc.page_content
            for doc in documents
        ]

        print("\n========== Reranker ==========")

        print(
            f"Query: {query}"
        )

        print(
            f"候选文档数量: {len(document_texts)}"
        )

        profile = config.model_profile()
        if profile["mode"] == "dashscope":
            url = str(profile["rerank_base_url"])
            request_payload = {
                "model": str(profile["rerank_model"]),
                "query": query,
                "documents": document_texts,
            }
        else:
            url = f"{profile['rerank_base_url']}/{profile['rerank_model']}"
            request_payload = {
                "query": query,
                "contexts": [{"text": t} for t in document_texts],
            }

        payload = json.dumps(request_payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {profile['rerank_api_key']}",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            response = json.loads(resp.read().decode())

        # -------------------------
        # 判断请求是否成功
        # -------------------------

        if profile["mode"] == "dashscope":
            if response.get("code") or response.get("message") and not response.get("output"):
                raise RuntimeError(f"DashScope Reranker 调用失败: {response}")
            results = response.get("results", [])
            if not results:
                results = (response.get("output") or {}).get("results", [])
        else:
            if not response.get("success", False):
                raise RuntimeError(f"Cloudflare Reranker 调用失败: {response}")
            results = response["result"]["response"]

        reranked_documents = []
        scores = []

        for result in results:
            index = result.get("index", result.get("id"))
            score = result.get("relevance_score", result.get("score"))
            if index is None or score is None:
                continue

            doc = documents[index]

            print(
                f"\nRerank Score: {score:.4f}"
            )

            print(
                f"来源: "
                f"{doc.metadata.get('source')}"
            )

            print(
                f"页码: "
                f"{doc.metadata.get('page')}"
            )

            print(
                f"内容: "
                f"{doc.page_content[:200]}"
            )

            reranked_documents.append(
                doc
            )
            scores.append(score)

        return reranked_documents, scores

# =========================================================
# 向量检索实现
# =========================================================
    def vector_search(self, query):

        print(
            "\n========== Vector Retrieval =========="
        )

        vector_docs = self.vector_store.similarity_search(
            query,
            k=config.vector_top_k,
        )

        print(
            f"Vector 返回 "
            f"{len(vector_docs)} 个文档"
        )

        reranked_docs, scores = self.rerank(
            query,
            vector_docs
        )

        print(
            "\n========== Vector Search Finished =========="
        )

        print(
            f"最终返回 "
            f"{len(reranked_docs)} 个文档"
        )

        return reranked_docs

# =========================================================
# 统一检索入口
# =========================================================
    def search(self, query, mode=None):

        current_mode = mode or config.default_retrieval_mode

        if current_mode == "vector":
            return self.vector_search(query)

        return self.hybrid_search(query)

# =========================================================
# 混合检索实现
# =========================================================
    def hybrid_search(self, query):

        # =====================================================
        # vector
        # =====================================================
        print(
            "\n========== Vector Retrieval =========="
        )
        vector_retriever = self.get_vector_retriever()

        vector_docs = (
            vector_retriever.invoke(query)
        )

        print(
            f"Vector 返回 "
            f"{len(vector_docs)} 个文档"
        )

        # =====================================================
        # BM25
        # =====================================================
        print(
            "\n========== BM25 Retrieval =========="
        )

        bm25_retriever = self.get_bm25_retriever()

        if bm25_retriever is None:
            print(
                "BM25 没有可用文档，"
                "直接使用 Vector 结果"
            )
            return vector_docs

        bm25_docs = bm25_retriever.invoke(query)

        print(
            f"BM25 返回 "
            f"{len(bm25_docs)} 个文档"
        )

        # =====================================================
        # RRF
        # =====================================================

        print(
            "\n========== RRF Fusion =========="
        )

        fused_docs = self._rrf_fusion(
            vector_docs,
            bm25_docs
        )

        print(
            f"RRF 返回 "
            f"{len(fused_docs)} 个候选文档"
        )

        # =====================================================
        # Reranker
        # =====================================================
        reranked_docs, scores = self.rerank(
            query,
            fused_docs
        )
        print(
            "\n========== Hybrid Search Finished =========="
        )

        print(
            f"最终返回 "
            f"{len(reranked_docs)} 个文档"
        )

        return reranked_docs

# =========================================================
# 测试
# =========================================================

if __name__ == "__main__":
    import sys

    service = VectorStoreService(
        OllamaEmbeddings(
            model=config.embedding_model_name,
            base_url=config.ollama_base_url,
        )
    )

    args = sys.argv[1:]
    mode = "hybrid"

    if "--vector" in args:
        mode = "vector"
        args.remove("--vector")
    elif "--hybrid" in args:
        mode = "hybrid"
        args.remove("--hybrid")

    query = " ".join(args).strip()
    if not query:
        query = "简单介绍下基于C++构建ZRDDS的方式"

    results = service.search(
        query,
        mode=mode,
    )

    print(
        "\n\n"
        "======================================"
    )

    print(
        f"最终 Reranker 检索结果 [{mode}]"
    )

    print(
        "======================================"
    )

    for i, doc in enumerate(
            results,
            start=1
    ):
        print(
            f"\n--- Final Result {i} ---"
        )

        print(
            "内容："
        )

        print(
            doc.page_content
        )

        print(
            "Metadata："
        )

        print(
            doc.metadata
        )
