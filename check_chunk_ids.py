from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import config_data as config

chroma = Chroma(
    collection_name=config.collection_name,
    embedding_function=OllamaEmbeddings(model=config.embedding_model_name, base_url=config.ollama_base_url),
    persist_directory=config.persist_directory,
)
data = chroma.get()
metadatas = data.get("metadatas", [])

# 检查 chunk_id 设置
chunk_ids = [m.get("chunk_id") for m in metadatas]
print(f"总chunks: {len(metadatas)}")
print(f"chunk_id None 数量: {sum(1 for c in chunk_ids if c is None)}")
print(f"chunk_id 有值数量: {sum(1 for c in chunk_ids if c is not None)}")

if chunk_ids[0] is not None:
    print(f"前5个chunk_id: {chunk_ids[:5]}")
    print(f"最大chunk_id: {max(c for c in chunk_ids if c is not None)}")
