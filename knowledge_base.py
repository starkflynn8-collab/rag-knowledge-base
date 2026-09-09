"""
文本处理，知识库构建
"""
import os

from langchain_community.tools.connery import service

import config_data as config
import hashlib
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from datetime import datetime
from corpus_cleaner import infer_doc_type, parse_version

def check_md5(md5_str: str):
    """检查传入的md5字符串是否已经被处理过了
    return False(md5未处理过)  True(已经处理过，已有记录)
    """
    if not os.path.exists(config.md5_path):
        # if进入表示文件不存在，那肯定没有处理过这个md5了
        open(config.md5_path, 'w', encoding='utf-8').close()
        return False
    else:
        for line in open(config.md5_path, 'r', encoding='utf-8').readlines():
            line = line.strip()  # 处理字符串前后的空格和回车
            if line == md5_str:
                return True  # 已处理过
        return False

def save_md5(md5_str: str):
    with open(config.md5_path, "a", encoding="utf-8") as f:
        f.write(md5_str + "\n")

def get_string_md5(input_str: str, encoding='utf-8'):
    """将传入的字符串转换为md5字符串"""

    # 将字符串转换为bytes字节数组
    str_bytes = input_str.encode(encoding=encoding)

    # 创建md5对象
    md5_obj = hashlib.md5()        # 得到md5对象
    md5_obj.update(str_bytes)      # 更新内容（传入即将要转换的字节数组）
    md5_hex = md5_obj.hexdigest()  # 得到md5的十六进制字符串

    return md5_hex

class KnowledgeBaseService(object):
    def __init__(self):
        self.chroma = Chroma(
            collection_name=config.collection_name,
            embedding_function=OllamaEmbeddings(
                model=config.embedding_model_name,
                base_url=config.ollama_base_url,
            ),
            persist_directory=config.persist_directory,
        )
        # 向量库构建，主要负责写入知识
        
        self.spliter = RecursiveCharacterTextSplitter( # 递归文本字符器，按自然文本边界划分，而非简单分割
            chunk_size=config.chunk_size,  # 分割后的文本段最大长度
            chunk_overlap=config.chunk_overlap,  # 连续文本段之间的字符重叠数量
            separators=config.separators,  # 自然段落划分的符号
            length_function=len,  # 使用Python自带的len函数做长度统计的依据
        )
        # 文本分割器创建

    def upload_documents(
            self,
            documents: list[Document],
            filename: str,
            file_md5: str = None,
            operator: str = "小虎",
    ) -> str:

        if not documents:
            return "[失败]文件没有解析出有效内容"

        # =========================
        # MD5去重
        # =========================

        if file_md5 and check_md5(file_md5):
            return "[跳过]内容已经存在知识库中"

        # =========================
        # 添加统一 Metadata
        # =========================

        inferred_doc_type = infer_doc_type(filename)
        version = parse_version(filename)

        for doc in documents:
            doc.metadata["source"] = filename
            doc.metadata["doc_type"] = doc.metadata.get("doc_type", inferred_doc_type)
            doc.metadata["version"] = doc.metadata.get("version", version)

            doc.metadata["create_time"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            doc.metadata["operator"] = operator

        # =========================
        # Document → Chunk
        # =========================

        chunks = self.spliter.split_documents(
            documents
        )

        # 获取当前全局chunk数量，用于全局编号
        existing_count = len(self.chroma.get().get("ids", []))

        for chunk_index, chunk in enumerate(chunks):
            global_id = existing_count + chunk_index
            chunk.metadata["chunk_id"] = global_id
            chunk.metadata["source_chunk_id"] = f"{filename}#{global_id}"
            if chunk.metadata.get("page") is None:
                chunk.metadata["page"] = "unknown"

        # =========================
        # Chunk → Embedding → Chroma
        # =========================

        batch_size = max(1, int(config.embedding_batch_size))

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            self.chroma.add_documents(batch)

        # =========================
        # 保存 MD5
        # =========================

        if file_md5:
            save_md5(file_md5)

        return (
            f"[成功]内容已成功载入向量库，"
            f"共生成 {len(chunks)} 个文本块，"
            f"按每批 {batch_size} 个文本块写入"
        )


if __name__ == '__main__':

    service = KnowledgeBaseService()

    documents = [
        Document(
            page_content="ZRDDS是一种基于DDS标准的通信产品。",
            metadata={}
        ),
        Document(
            page_content="ZRDDS支持多种QoS策略。",
            metadata={}
        )
    ]

    result = service.upload_documents(
        documents=documents,
        filename="test.txt"
    )

    print(result)
