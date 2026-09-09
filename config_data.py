import os
from dotenv import load_dotenv

load_dotenv()

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

md5_path = "./md5.text"

# Chroma
collection_name = "rag"
persist_directory = "./chroma_db"

# spliter
chunk_size = 1000
chunk_overlap = 100
separators = ["\n\n", "\n", ".", "!", "?", "。", "！", "？", " ", ""] # 划分按“章节——>段落——>句子——>字符”
max_split_char_number = 1000

vector_top_k = 10
bm25_top_k = 10
rrf_top_k = 10
rerank_top_k = 5
rrf_const = 60
default_retrieval_mode = "hybrid"

#拒绝阈值：当rerank结果中最高得分低于这个阈值时判断本知识库无法回答该问题
refusal_score_threshold = 0.3

# 引用粒度阈值：分数越高，引用越精细
citation_granularity_thresholds = {
    "fine": 0.7,    # 精细：来源+页码+chunk_id+摘要
    "medium": 0.4,  # 中等：来源+页码
    # 低于 medium 则为 coarse（仅来源）
}

embedding_provider = "ollama"
embedding_model_name = "bge-m3"
ollama_base_url = "http://localhost:11434"
embedding_batch_size = 4

chat_model_name = "@cf/meta/llama-3.2-3b-instruct"
rerank_model_name = "@cf/baai/bge-reranker-base"

cloudflare_chat_base_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1"
cloudflare_rerank_base_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run"

# 一个会话的唯一标识
session_config = {
        "configurable":{
            "session_id":"user_001",
        }
    }

