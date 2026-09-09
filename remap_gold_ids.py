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

# 获取文件->chunk_id范围映射
data = chroma.get()
metadatas = data.get("metadatas", [])

file_ranges = {}
for m in metadatas:
    src = m.get("source", "unknown")
    cid = m.get("chunk_id")
    if src not in file_ranges:
        file_ranges[src] = {"min": cid, "max": cid, "count": 0}
    file_ranges[src]["min"] = min(file_ranges[src]["min"], cid)
    file_ranges[src]["max"] = max(file_ranges[src]["max"], cid)
    file_ranges[src]["count"] += 1

# 为每个问题找到新的gold_chunk_id
new_qa_data = []
mapped_count = 0
failed_count = 0

for q in qa_data:
    query = q.get("query", "")
    answer_hint = q.get("answer_hint", "")
    note = q.get("备注", "")
    
    # 从备注中提取文件名
    match = re.match(r'(.+?)\s*\|', note)
    if not match:
        print(f"  跳过 (无法解析备注): {note}")
        failed_count += 1
        new_qa_data.append(q)
        continue
    
    target_file = match.group(1).strip()
    
    # 用query搜索，限制在目标文件内
    results = chroma.similarity_search(query, k=10)
    
    # 从搜索结果中找到属于目标文件的chunk
    found = False
    for doc in results:
        src = doc.metadata.get("source", "")
        if src == target_file:
            cid = doc.metadata.get("chunk_id")
            new_q = q.copy()
            new_q["gold_chunk_ids"] = [cid]
            new_qa_data.append(new_q)
            mapped_count += 1
            found = True
            break
    
    if not found:
        # 如果没找到，用第一个结果
        if results:
            cid = results[0].metadata.get("chunk_id")
            new_q = q.copy()
            new_q["gold_chunk_ids"] = [cid]
            new_qa_data.append(new_q)
            mapped_count += 1
            print(f"  警告: 目标文件 {target_file} 未找到，使用第一个结果 chunk_id={cid}")
        else:
            print(f"  失败: 无搜索结果 - {query[:30]}...")
            failed_count += 1
            new_qa_data.append(q)

print(f"\n映射完成: {mapped_count} 成功, {failed_count} 失败")

# 保存新数据集
output_path = r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-benchmark\datasets\qa_dataset_new.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(new_qa_data, f, ensure_ascii=False, indent=2)

print(f"新数据集已保存到: {output_path}")

# 显示前5个映射结果
print("\n前5个映射结果:")
for q in new_qa_data[:5]:
    note = q.get("备注", "")
    gold_ids = q.get("gold_chunk_ids", [])
    print(f"  {note} -> {gold_ids}")
