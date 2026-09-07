"""批量导入知识库文件。

用法：
    python batch_ingest.py "D:\\path\\to\\docs"
    python batch_ingest.py "D:\\path\\to\\docs" --dry-run
    python batch_ingest.py "D:\\path\\to\\docs" --include-noise-html
"""

import argparse
import hashlib
from pathlib import Path

from document_loader import DocumentLoaderService
from knowledge_base import KnowledgeBaseService
from corpus_cleaner import (
    infer_doc_type,
    iter_supported_files,
    load_html,
    normalize_source,
)


def file_md5(file_path: Path) -> str:
    md5 = hashlib.md5()

    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            md5.update(chunk)

    return md5.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="批量导入目录中的知识库文件")
    parser.add_argument("path", help="要导入的文件或目录路径")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只扫描文件，不写入知识库",
    )
    parser.add_argument(
        "--include-noise-html",
        action="store_true",
        help="导入 Doxygen/Javadoc 的索引、搜索、源码等噪声 HTML",
    )
    parser.add_argument(
        "--operator",
        default="小虎",
        help="导入操作者名称",
    )
    args = parser.parse_args()

    input_path = Path(args.path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"路径不存在：{input_path}")

    if input_path.is_file():
        root = input_path.parent
        candidates = [(input_path, Path(input_path.name), "keep")]
    else:
        root = input_path
        candidates = list(iter_supported_files(root, args.include_noise_html))

    kept_files = [
        item for item in candidates
        if item[2] == "keep"
    ]
    skipped_noise = [
        item for item in candidates
        if item[2] == "noise-html"
    ]

    print(f"扫描路径：{input_path}")
    print(f"可导入文件：{len(kept_files)}")
    print(f"跳过噪声 HTML：{len(skipped_noise)}")

    if args.dry_run:
        for _, relative_path, _ in kept_files:
            print(f"[待导入] {normalize_source(Path(relative_path))}")
        for _, relative_path, _ in skipped_noise:
            print(f"[跳过] {normalize_source(Path(relative_path))}")
        return

    loader = DocumentLoaderService()
    service = KnowledgeBaseService()

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for file_path, relative_path, _ in kept_files:
        source = normalize_source(Path(relative_path))

        try:
            if file_path.suffix.lower() in {".html", ".htm"}:
                documents = load_html(file_path)
            else:
                documents = loader.load(str(file_path))

            for doc in documents:
                doc.metadata["doc_type"] = infer_doc_type(Path(relative_path))

            result = service.upload_documents(
                documents=documents,
                filename=source,
                file_md5=file_md5(file_path),
                operator=args.operator,
            )

            if result.startswith("[跳过]"):
                skipped_count += 1
            else:
                success_count += 1

            print(f"{result} {source}")

        except Exception as e:
            failed_count += 1
            print(f"[失败] {source}: {e}")

    print("=" * 60)
    print(f"导入完成：成功 {success_count}，跳过 {skipped_count}，失败 {failed_count}")


if __name__ == "__main__":
    main()
