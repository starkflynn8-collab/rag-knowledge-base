import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-knowledge-base")
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import config_data as config

chroma = Chroma(
    collection_name=config.collection_name,
    embedding_function=OllamaEmbeddings(model=config.embedding_model_name, base_url=config.ollama_base_url),
    persist_directory=config.persist_directory,
)

# 检查ZRDDSGen用户手册.html的所有chunks
target = "ZRDDSGen\u7528\u6237\u624b\u518c.html"
data = chroma.get(where={"source": target})
ids = data.get("ids", [])
metadatas = data.get("metadatas", [])
contents = data.get("documents", [])

print(f"ZRDDSGen用户手册.html chunks数量: {len(ids)}")
for i, (cid, meta) in enumerate(zip(ids, metadatas)):
    chunk_id = meta.get("chunk_id")
    content = contents[i][:120] if i < len(contents) else ""
    print(f"  chunk {i}: id={cid}, chunk_id={chunk_id}")
    print(f"    content: {content}...")
