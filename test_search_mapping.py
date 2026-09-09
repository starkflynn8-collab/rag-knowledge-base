import json
import sys
import re
sys.path.insert(0, r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-knowledge-base")

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import config_data as config

# 加载Chroma
chroma = Chroma(
    collection_name=config.collection_name,
    embedding_function=OllamaEmbeddings(model=config.embedding_model_name, base_url=config.ollama_base_url),
    persist_directory=config.persist_directory,
)

# 读取原始qa_dataset
with open(r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-benchmark\datasets\qa_dataset.json", "r", encoding="utf-8") as f:
    qa_data = json.load(f)

# 测试前5个问题，用answer_hint搜索
print("测试用answer_hint搜索对应chunk:")
for q in qa_data[:5]:
    query = q.get("query", "")
    answer_hint = q.get("answer_hint", "")
    old_gold_ids = q.get("gold_chunk_ids", [])
    note = q.get("备注", "")
    
    # 用query搜索
    results = chroma.similarity_search(query, k=3)
    
    print(f"\n问题: {query[:50]}...")
    print(f"  原始gold_chunk_ids: {old_gold_ids}")
    print(f"  备注: {note}")
    print(f"  搜索结果:")
    for i, doc in enumerate(results):
        cid = doc.metadata.get("chunk_id", "N/A")
        src = doc.metadata.get("source", "N/A")
        print(f"    [{i}] chunk_id={cid}, source={src[:50]}...")
