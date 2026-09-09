import json
import sys
import os
sys.path.insert(0, r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-knowledge-base")

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import config_data as config

# 读取原始qa_dataset
with open(r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-benchmark\datasets\qa_dataset.json", "r", encoding="utf-8") as f:
    qa_data = json.load(f)

print(f"原始问题数量: {len(qa_data)}")

# 加载Chroma获取文件->chunk_id映射
chroma = Chroma(
    collection_name=config.collection_name,
    embedding_function=OllamaEmbeddings(model=config.embedding_model_name, base_url=config.ollama_base_url),
    persist_directory=config.persist_directory,
)
data = chroma.get()
metadatas = data.get("metadatas", [])

# 建立文件->chunk_id范围映射
file_ranges = {}
for m in metadatas:
    src = m.get("source", "unknown")
    cid = m.get("chunk_id")
    if src not in file_ranges:
        file_ranges[src] = {"min": cid, "max": cid, "count": 0}
    file_ranges[src]["min"] = min(file_ranges[src]["min"], cid)
    file_ranges[src]["max"] = max(file_ranges[src]["max"], cid)
    file_ranges[src]["count"] += 1

print(f"文件数量: {len(file_ranges)}")

# 显示前5个文件的映射
print("\n当前文件->chunk_id范围:")
for src in sorted(file_ranges.keys())[:5]:
    info = file_ranges[src]
    print(f"  {src}: {info['min']}-{info['max']} ({info['count']} chunks)")

# 分析原始数据集的问题分布
print("\n原始数据集前10个问题:")
for q in qa_data[:10]:
    note = q.get("备注", "")
    gold_ids = q.get("gold_chunk_ids", [])
    print(f"  {note} -> gold_chunk_ids: {gold_ids}")
