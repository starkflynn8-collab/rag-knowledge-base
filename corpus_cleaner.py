"""语料清洗和元数据识别工具。"""

import os
import re
from pathlib import Path

from bs4 import BeautifulSoup
from langchain_community.document_loaders import BSHTMLLoader
from langchain_core.documents import Document


VERSION_RE = re.compile(r"v?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".csv", ".docx", ".html", ".htm"}

NOISE_HTML_BASENAMES = {
    "index.html",
    "annotated.html",
    "classes.html",
    "functions.html",
    "namespaces.html",
    "files.html",
    "pages.html",
    "package-summary.html",
}


def parse_version(filename: str) -> str:
    match = VERSION_RE.search(os.path.basename(filename))
    return match.group(1) if match else "unknown"


def is_noise_html(relative_path) -> bool:
    path = Path(relative_path)
    parts = [part.lower() for part in path.parts]
    base = parts[-1]

    if "search" in parts or "static" in parts:
        return True
    if base in NOISE_HTML_BASENAMES:
        return True
    if base.endswith("-members.html"):
        return True
    if base.endswith("-example.html"):
        return True
    if base.startswith("dir_") and base.endswith(".html"):
        return True
    if base.startswith("globals_") and base.endswith(".html"):
        return True
    if base.endswith("_source.html"):
        return True

    return False


def infer_doc_type(filename: str) -> str:
    normalized = str(filename).replace("/", "\\").lower()
    suffix = os.path.splitext(normalized)[1]
    parts = normalized.split("\\")

    if "cdoc" in parts or "c" in parts:
        return "c"
    if "cppdoc" in parts or "cpp" in parts:
        return "cpp"
    if "javadoc" in parts or "java" in parts:
        return "java"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    if suffix == ".csv":
        return "csv"
    if suffix == ".txt":
        return "txt"
    if suffix in (".html", ".htm"):
        return "html"

    return "unknown"


def load_html(file_path: Path):
    last_error = None

    for encoding in ("utf-8", "gbk", "gb18030"):
        try:
            return BSHTMLLoader(
                str(file_path),
                open_encoding=encoding,
                get_text_separator="\n",
                bs_kwargs={"features": "html.parser"},
            ).load()
        except UnicodeDecodeError as e:
            last_error = e

    raw = file_path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    return [
        Document(
            page_content=soup.get_text("\n"),
            metadata={
                "source": file_path.name,
                "title": title,
                "decode_warning": str(last_error),
            },
        )
    ]


def iter_supported_files(root: Path, include_noise_html: bool):
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            continue

        relative_path = file_path.relative_to(root)
        if suffix in {".html", ".htm"} and not include_noise_html:
            if is_noise_html(relative_path):
                yield file_path, relative_path, "noise-html"
                continue

        yield file_path, relative_path, "keep"


def normalize_source(relative_path) -> str:
    return str(relative_path).replace("/", "\\")
