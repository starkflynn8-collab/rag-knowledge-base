from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import config_data as config

chroma = Chroma(
    collection_name=config.collection_name,
    embedding_function=OllamaEmbeddings(model=config.embedding_model_name, base_url=config.ollama_base_url),
    persist_directory=config.persist_directory,
)

# 检查 Chroma 的 id 格式
data = chroma.get()
ids = data.get("ids", [])
metadatas = data.get("metadatas", [])

print(f"总chunks: {len(ids)}")
print(f"前5个id: {ids[:5]}")

# 检查 source 分布
sources = {}
for m in metadatas:
    src = m.get("source", "unknown")
    sources[src] = sources.get(src, 0) + 1

print(f"\n共 {len(sources)} 个文件")
print("前10个文件:")
for i, (src, count) in enumerate(sorted(sources.items(), key=lambda x: -x[1])[:10]):
    print(f"  {src}: {count} chunks")
