import hashlib
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

md5_path = str(PROJECT_ROOT / "md5.text")

# Chroma
collection_name = "rag"
persist_directory = str(PROJECT_ROOT / "chroma_db")

# Authentication and application data
auth_db_path = str(PROJECT_ROOT / "data" / "auth.sqlite3")
auth_cookie_name = os.getenv("AUTH_COOKIE_NAME", "ddsrag_session")
auth_cookie_max_age = int(os.getenv("AUTH_COOKIE_MAX_AGE", str(7 * 24 * 3600)))
auth_cookie_secure = os.getenv("AUTH_COOKIE_SECURE", "false").strip().lower() == "true"
auth_secret_path = PROJECT_ROOT / "data" / "auth_secret.key"


def _load_auth_secret() -> str:
    configured = os.getenv("AUTH_SECRET_KEY", "").strip()
    if configured:
        return configured

    # Stable development fallback; production deployments must configure AUTH_SECRET_KEY.
    return hashlib.sha256(
        f"DDSRag-v2:{PROJECT_ROOT}".encode("utf-8")
    ).hexdigest()


auth_secret_key = _load_auth_secret()
# HTML 原始文档目录：知识库中的 HTML source 是相对于该目录的路径
html_source_root = os.getenv(
    "HTML_SOURCE_ROOT",
    r"D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc\html",
)

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


cloudflare_chat_model_name = os.getenv(
    "CLOUDFLARE_CHAT_MODEL",
    "@cf/meta/llama-3.2-3b-instruct",
)
cloudflare_rerank_model_name = os.getenv(
    "CLOUDFLARE_RERANK_MODEL",
    "@cf/baai/bge-reranker-base",
)
dashscope_chat_model_name = os.getenv("DASHSCOPE_CHAT_MODEL", "qwen-plus")
dashscope_rerank_model_name = os.getenv("DASHSCOPE_RERANK_MODEL", "qwen3-rerank")

model_mode = os.getenv(
    "MODEL_MODE",
    "dashscope" if DASHSCOPE_API_KEY else "cloudflare",
).strip().lower()
if model_mode not in {"cloudflare", "dashscope"}:
    model_mode = "cloudflare"

chat_model_name = (
    dashscope_chat_model_name if model_mode == "dashscope" else cloudflare_chat_model_name
)
rerank_model_name = (
    dashscope_rerank_model_name if model_mode == "dashscope" else cloudflare_rerank_model_name
)

cloudflare_chat_base_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1"
cloudflare_rerank_base_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run"
dashscope_chat_base_url = os.getenv(
    "DASHSCOPE_CHAT_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
).rstrip("/")
dashscope_rerank_base_url = os.getenv(
    "DASHSCOPE_RERANK_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
).rstrip("/")


def model_profile(mode: str | None = None) -> dict[str, str | bool]:
    current_mode = (mode or model_mode).strip().lower()
    if current_mode == "dashscope":
        return {
            "mode": "dashscope",
            "chat_provider": "dashscope",
            "chat_model": dashscope_chat_model_name,
            "chat_base_url": dashscope_chat_base_url,
            "chat_api_key": DASHSCOPE_API_KEY or "",
            "chat_api_key_configured": bool(DASHSCOPE_API_KEY),
            "rerank_provider": "dashscope",
            "rerank_model": dashscope_rerank_model_name,
            "rerank_base_url": dashscope_rerank_base_url,
            "rerank_api_key": DASHSCOPE_API_KEY or "",
            "rerank_api_key_configured": bool(DASHSCOPE_API_KEY),
        }
    return {
        "mode": "cloudflare",
        "chat_provider": "cloudflare",
        "chat_model": cloudflare_chat_model_name,
        "chat_base_url": cloudflare_chat_base_url,
        "chat_api_key": CLOUDFLARE_API_TOKEN or "",
        "chat_api_key_configured": bool(CLOUDFLARE_API_TOKEN),
        "rerank_provider": "cloudflare",
        "rerank_model": cloudflare_rerank_model_name,
        "rerank_base_url": cloudflare_rerank_base_url,
        "rerank_api_key": CLOUDFLARE_API_TOKEN or "",
        "rerank_api_key_configured": bool(CLOUDFLARE_API_TOKEN),
    }


def set_model_mode(mode: str) -> dict[str, str | bool]:
    global model_mode, chat_model_name, rerank_model_name
    normalized = str(mode or "").strip().lower()
    if normalized not in {"cloudflare", "dashscope"}:
        raise ValueError("模型模式必须是 cloudflare 或 dashscope")
    model_mode = normalized
    profile = model_profile(normalized)
    chat_model_name = str(profile["chat_model"])
    rerank_model_name = str(profile["rerank_model"])
    return profile

# 一个会话的唯一标识
session_config = {
        "configurable":{
            "session_id":"user_001",
        }
    }

