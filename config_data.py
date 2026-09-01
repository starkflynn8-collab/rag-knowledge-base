import os
from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

md5_path = "./md5.text"

# Chroma
collection_name = "rag"
persist_directory = "./chroma_db"

# spliter
chunk_size = 1000
chunk_overlap = 100
separators = ["\n\n", "\n", ".", "!", "?", "。", "！", "？", " ", ""] # 划分按“章节——>段落——>句子——>字符”
max_split_char_number = 1000

similarity_threshold = 1 # 检索返回的文档数量

embedding_model_name = "text-embedding-v4"
chat_model_name = "qwen3-max"

# 一个会话的唯一标识
session_config = {
        "configurable":{
            "session_id":"user_001",
        }
    }