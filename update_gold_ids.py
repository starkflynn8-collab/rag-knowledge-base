import json
import sys
import re
sys.path.insert(0, r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-knowledge-base")

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
import config_data as config

# 读取原始qa_dataset
input_path = r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-benchmark\datasets\qa_dataset.json"
output_path = r"C:\Users\Administrator\Desktop\SEU\code\summer2\rag-benchmark\datasets\qa_dataset_new.json"

with open(input_path, "r", encoding="utf-8") as f:
    qa_data = json.load(f)

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

# 显示几个文件的映射
print("\nZRDDSGen用户手册.html 的映射:")
for src in file_ranges:
    if "ZRDDSGen" in src:
        info = file_ranges[src]
        print(f"  {src}: {info['min']}-{info['max']} ({info['count']} chunks)")

# 更新qa_dataset中的gold_chunk_ids
updated_count = 0
skipped_count = 0
new_qa_data = []

for q in qa_data:
    note = q.get("备注", "")
    old_gold_ids = q.get("gold_chunk_ids", [])
    
    # 解析备注: "ZRDDSGen用户手册.html | chunk 35"
    match = re.match(r'(.+?)\s*\|\s*chunk\s+(\d+)', note)
    if not match:
        print(f"  跳过 (无法解析备注): {note}")
        skipped_count += 1
        new_qa_data.append(q)
        continue
    
    filename = match.group(1).strip()
    old_chunk_offset = int(match.group(2))
    
    # 查找文件在当前Chroma中的新范围
    if filename not in file_ranges:
        print(f"  跳过 (文件不存在): {filename}")
        skipped_count += 1
        new_qa_data.append(q)
        continue
    
    file_info = file_ranges[filename]
    file_min = file_info["min"]
    file_count = file_info["count"]
    
    # 计算旧的chunk在文件内的偏移（假设原始数据集是从文件开头开始编号的）
    # 原始的gold_chunk_ids是全局编号，需要减去文件在原始项目中的起始chunk_id
    # 但我们没有原始项目的映射，所以假设旧的offset是文件内偏移
    
    # 检查old_gold_ids是否在文件范围内
    # 如果old_gold_ids[0] > file_count，说明是全局编号
    # 我们需要文件在原始项目中的起始位置
    
    # 简单假设：old_gold_ids中的值是文件内偏移（0-based）
    if old_gold_ids[0] < file_count:
        # 文件内偏移，直接映射
        new_gold_ids = [file_min + old_id for old_id in old_gold_ids]
    else:
        # 全局编号，需要计算
        # 这里需要原始项目的映射，但我们没有
        # 打印出来让用户确认
        print(f"  注意: {filename} old_gold_ids={old_gold_ids}, file_count={file_count}")
        # 假设是文件内偏移+文件在原始项目的起始位置
        # 但由于我们没有原始信息，先跳过
        skipped_count += 1
        new_qa_data.append(q)
        continue
    
    # 更新
    new_q = q.copy()
    new_q["gold_chunk_ids"] = new_gold_ids
    new_qa_data.append(new_q)
    updated_count += 1

print(f"\n更新完成: {updated_count} 个问题已更新, {skipped_count} 个跳过")

# 保存新数据集
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(new_qa_data, f, ensure_ascii=False, indent=2)

print(f"新数据集已保存到: {output_path}")
