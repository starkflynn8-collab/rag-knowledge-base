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

# 按 source 分组，显示每个文件的 chunk_id 范围
sources = {}
for m in metadatas:
    src = m.get("source", "unknown")
    cid = m.get("chunk_id")
    if src not in sources:
        sources[src] = {"min": cid, "max": cid, "count": 0}
    sources[src]["min"] = min(sources[src]["min"], cid)
    sources[src]["max"] = max(sources[src]["max"], cid)
    sources[src]["count"] += 1

print(f"总chunks: {len(metadatas)}")
print("\n文件 chunk_id 范围:")
for src in sorted(sources.keys()):
    info = sources[src]
    print(f"  {src}: {info['min']}-{info['max']} ({info['count']} chunks)")
