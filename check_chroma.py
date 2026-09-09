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
print(f"总chunk数: {len(metadatas)}")
if metadatas:
    print("前5个metadata:")
    for i, m in enumerate(metadatas[:5]):
        print(f"  [{i}] chunk_id={m.get('chunk_id')}, source={m.get('source')}, source_chunk_id={m.get('source_chunk_id')}")
