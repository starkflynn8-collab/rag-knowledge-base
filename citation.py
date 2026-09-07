"""引用格式化工具。"""

from langchain_core.documents import Document


def format_citation(metadata: dict) -> str:
    source = metadata.get("source", "未知来源")
    doc_type = metadata.get("doc_type", "")
    page = metadata.get("page_label", metadata.get("page", "unknown"))
    version = metadata.get("version", "unknown")
    chunk_id = metadata.get("chunk_id", "unknown")
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
    citation = format_citation(doc.metadata or {})
    return (
        f"[{index}] 出处: {citation}\n"
        f"{doc.page_content}"
    )
