"""负责上传文件的解析"""

from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    CSVLoader,
)
from corpus_cleaner import load_html


class DocumentLoaderService:

    def load(self, file_path: str) -> list[Document]:

        suffix = Path(file_path).suffix.lower()

        if suffix == ".pdf":
            return self._load_pdf(file_path)

        elif suffix == ".txt":
            return self._load_txt(file_path)

        elif suffix == ".csv":
            return self._load_csv(file_path)

        elif suffix == ".docx":
            return self._load_docx(file_path)

        elif suffix in [".html", ".htm"]:
            return self._load_html(file_path)

        else:
            raise ValueError(f"不支持的文件类型：{suffix}")

    def _load_pdf(self, file_path):
        loader = PyPDFLoader(file_path)
        return loader.load()

    def _load_txt(self, file_path):
        loader = TextLoader(
            file_path,
            encoding="utf-8"
        )
        return loader.load()

    def _load_csv(self, file_path):
        loader = CSVLoader(file_path)
        return loader.load()

    def _load_docx(self, file_path):
        loader = Docx2txtLoader(file_path)
        return loader.load()

    def _load_html(self, file_path):
        return load_html(Path(file_path))
