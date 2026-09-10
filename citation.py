"""引用格式化工具。"""

import hashlib

from langchain_core.documents import Document


def resolve_chunk_id(metadata: dict, content: str = "") -> str:
    """返回稳定的 chunk 标识，兼容旧数据中缺失 chunk_id 的记录。"""
    chunk_id = metadata.get("chunk_id")
    if chunk_id not in (None, "", "unknown"):
        return str(chunk_id)

    source_chunk_id = metadata.get("source_chunk_id")
    if source_chunk_id not in (None, "", "unknown"):
        return str(source_chunk_id).split("#")[-1]

    source = str(metadata.get("source", "unknown"))
    page = str(metadata.get("page_label", metadata.get("page", "unknown")))
    digest = hashlib.md5(f"{source}|{page}|{content}".encode("utf-8")).hexdigest()[:10]
    return f"legacy-{digest}"


def format_citation(metadata: dict, content: str = "") -> str:
    source = metadata.get("source", "未知来源")
    doc_type = metadata.get("doc_type", "")
    page = metadata.get("page_label", metadata.get("page", "unknown"))
    version = metadata.get("version", "unknown")
    chunk_id = resolve_chunk_id(metadata, content)
    symbol = metadata.get("symbol", "")

    if doc_type in ("pdf", "pptx") and page not in (None, "", "unknown"):
        location = f"p.{page}"
    else:
        location = f"chunk {chunk_id}"

    label = symbol if symbol else source
    parts = [str(label), str(location)]
    if version and version != "unknown":
        parts.append(f"v{version}")

    return " | ".join(parts)


def format_document_block(index: int, doc: Document) -> str:
    citation = format_citation(doc.metadata or {}, doc.page_content)
    return (
        f"[{index}] 出处: {citation}\n"
        f"{doc.page_content}"
    )
