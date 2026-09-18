# DDSRag v2 项目说明

DDSRag v2 是面向 ZRDDS / DDS 产品资料的知识库构建与开发调试问答系统。系统以本地知识库为基础，通过 RAG 流程将企业文档、API 文档、安装配置手册和故障排查资料转化为可检索、可引用、可评测的技术问答能力。

当前版本已经从早期 Streamlit 原型升级为 `Vue3 + FastAPI + RAG 服务层` 的前后端项目，并加入登录注册、权限控制、知识库管理、引用追溯、双模型模式和评测接口。


## 1. 功能概览

- 知识库构建：支持 PDF、TXT、CSV、DOCX、HTML / HTM 文件解析、清洗、切分、向量化和入库。
- 批量导入：支持命令行目录导入，也支持前端批量上传。
- 问答助手：支持 DDS 安装配置、API 使用、QoS 设置、故障排查等技术问答。
- 混合检索：向量检索 + BM25 关键词检索 + RRF 融合 + Rerank 重排。
- 引用追溯：回答返回引用编号，可查看 PDF 片段或跳转 HTML 原文页面。
- 拒答机制：资料不足或相关性过低时明确提示，降低模型无依据生成风险。
- 会话管理：支持新建、编辑标题、删除会话和清空当前会话历史。
- 权限控制：支持注册登录、管理员后台、账号禁用、上传权限和模型切换权限。
- 双模型模式：支持阿里百炼和 Cloudflare 两套 LLM / Rerank 配置。
- 评测适配：提供 `/retrieve`、`/generate` 兼容接口，便于 rag-benchmark 接入。

## 2. 技术架构

```text
Vue3 前端
  -> FastAPI 接口层
  -> AppServices 业务编排层
  -> RagService / VectorStoreService / KnowledgeBaseService
  -> Chroma / BM25 / Ollama Embedding / Rerank / LLM
```

主要技术栈：

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3、Vite |
| 后端 | FastAPI、Uvicorn、Pydantic |
| RAG 编排 | LangChain |
| 向量库 | Chroma |
| 本地 Embedding | Ollama `bge-m3` |
| 关键词检索 | BM25 |
| 生成模型 | 阿里百炼 `qwen-plus`，可切换 Cloudflare |
| 重排模型 | 阿里百炼 `qwen3-rerank`，可切换 Cloudflare |
| 用户与会话 | SQLite、Cookie Session |

## 3. 目录结构

```text
DDSRag - v2/
├─ backend/                 FastAPI 后端接口、认证依赖、批量上传逻辑
├─ frontend/                Vue3 前端项目
├─ chroma_db/               Chroma 向量库，本地运行数据，不建议提交到 Git
├─ data/                    用户、权限、会话 SQLite 数据，不建议提交到 Git
├─ chat_history/            旧版历史记录目录，保留兼容迁移
├─ docs/                    项目文档
├─ app_qa.py                旧 Streamlit 问答入口
├─ app_file_uploader.py     旧 Streamlit 单文件上传入口
├─ batch_ingest.py          命令行批量导入脚本
├─ config_data.py           模型、检索、路径和认证配置
├─ document_loader.py       文档解析入口
├─ corpus_cleaner.py        HTML 清洗、噪声过滤、文档类型识别
├─ knowledge_base.py        文档切分、metadata、embedding、写入 Chroma
├─ vector_stores.py         向量检索、BM25、RRF、Rerank
├─ rag.py                   Prompt、生成模型、历史消息链
├─ auth_store.py            用户、权限、会话历史 SQLite 存储
├─ citation.py              引用格式化与 chunk id 解析
├─ requirements.txt         Python 依赖
└─ .env.example             环境变量示例
```

## 4. 环境准备

### 4.1 Python 环境

建议使用项目内 `.venv`。如果项目已经带有可用 `.venv`，直接激活即可：

```powershell
cd "D:\project\DDS\DDSRag - v2"
.\.venv\Scripts\Activate.ps1
```

如果需要重新创建环境：

```powershell
cd "D:\project\DDS\DDSRag - v2"
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果本机没有 Python 3.13，也可以使用项目依赖兼容的 Python 3.11+ 环境，但建议团队成员尽量保持版本一致。

### 4.2 Node 环境

前端需要 Node.js 和 npm。首次运行前安装前端依赖：

```powershell
cd "D:\project\DDS\DDSRag - v2\frontend"
npm install
```

### 4.3 Ollama 本地 Embedding

当前 embedding 固定使用本地 Ollama 的 `bge-m3`：

```powershell
ollama serve
ollama pull bge-m3
```

如果 `ollama serve` 已经作为后台服务运行，可以只执行 `ollama pull bge-m3`。

## 5. 环境变量配置

复制 `.env.example` 为 `.env`：

```powershell
cd "D:\project\DDS\DDSRag - v2"
copy .env.example .env
```

至少需要配置阿里百炼 API Key：

```text
DASHSCOPE_API_KEY=你的百炼APIKey
MODEL_MODE=dashscope
DASHSCOPE_CHAT_MODEL=qwen-plus
DASHSCOPE_RERANK_MODEL=qwen3-rerank
DASHSCOPE_CHAT_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-api/v1/reranks
```

如果需要使用 Cloudflare 模式，再配置：

```text
CLOUDFLARE_ACCOUNT_ID=你的Cloudflare账号ID
CLOUDFLARE_API_TOKEN=你的Cloudflare Token
CLOUDFLARE_CHAT_MODEL=@cf/meta/llama-3.2-3b-instruct
CLOUDFLARE_RERANK_MODEL=@cf/baai/bge-reranker-base
```

认证相关配置：

```text
AUTH_SECRET_KEY=replace_with_a_long_random_secret
AUTH_COOKIE_NAME=ddsrag_session
AUTH_COOKIE_MAX_AGE=604800
AUTH_COOKIE_SECURE=false
```

本地开发可以使用 `.env.example` 中的默认写法。正式部署时必须设置足够长、随机且保密的 `AUTH_SECRET_KEY`，并根据 HTTPS 情况设置 `AUTH_COOKIE_SECURE=true`。

HTML 原文跳转目录默认配置在 `config_data.py`：

```text
D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc\html
```

如果其他电脑路径不同，可以在 `.env` 中增加：

```text
HTML_SOURCE_ROOT=D:\your\path\to\ZRDDS\doc\html
```

## 6. 启动项目

### 6.1 启动后端

打开第一个终端：

```powershell
cd "D:\project\DDS\DDSRag - v2"
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：

```text
http://127.0.0.1:8000
```

健康检查接口：

```text
http://127.0.0.1:8000/api/health
```

### 6.2 启动前端

打开第二个终端：

```powershell
cd "D:\project\DDS\DDSRag - v2\frontend"
npm run dev
```

浏览器访问：

```text
http://localhost:5173
```

### 6.3 默认账号

系统初始化时会准备演示账号，常用账号如下：

```text
管理员：admin / admin123
普通用户：student / student123
```

如果当前数据库已经被修改过，以本地 `data/auth.sqlite3` 中的数据为准。正式交付或部署前应修改默认密码。

## 7. 推荐使用流程

1. 启动 Ollama，并确认 `bge-m3` 可用。
2. 启动 FastAPI 后端。
3. 启动 Vue 前端。
4. 使用管理员账号登录。
5. 在“系统状态”页检查 Embedding、LLM、Rerank 和知识库状态。
6. 在“知识库”页上传或批量导入文档。
7. 在“问答助手”页提问并检查引用。
8. 如需评测，使用 rag-benchmark 连接后端兼容接口。

## 8. 知识库入库方式

### 8.1 前端单文件上传

进入 Vue 前端“知识库”页面，选择文件上传。支持：

```text
pdf / txt / csv / docx / html / htm
```

上传需要当前用户具备上传权限。管理员可在“用户管理”页分配权限。

### 8.2 前端批量上传

“知识库”页面支持批量选择文件上传。后端会将文件写入临时批次目录，再调用统一入库流程。

### 8.3 命令行批量导入目录

预览扫描，不写入知识库：

```powershell
cd "D:\project\DDS\DDSRag - v2"
.\.venv\Scripts\python.exe batch_ingest.py "D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc" --dry-run
```

正式导入：

```powershell
.\.venv\Scripts\python.exe batch_ingest.py "D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc"
```

只导入 HTML 文档目录：

```powershell
.\.venv\Scripts\python.exe batch_ingest.py "D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc\html"
```

默认会过滤 Doxygen / Javadoc 生成的低价值噪声页，例如：

```text
index.html
classes.html
functions.html
files.html
pages.html
*-members.html
*_source.html
search/
static/
```

如果确实要导入这些噪声页，可以增加：

```powershell
--include-noise-html
```

一般不建议开启该参数，因为索引页、搜索页和源码页会污染检索结果。

## 9. RAG 流程说明

### 9.1 离线知识库构建

```text
原始文档
  -> 文档解析
  -> HTML / 文本清洗
  -> RecursiveCharacterTextSplitter 切分
  -> metadata 补充
  -> Ollama bge-m3 向量化
  -> Chroma 持久化入库
  -> md5.text 记录去重
```

入库时会保存以下 metadata：

| 字段 | 含义 |
|---|---|
| `source` | 来源文件名或相对路径 |
| `doc_type` | `pdf`、`html`、`c`、`cpp`、`java`、`docx`、`csv`、`txt` 等 |
| `version` | 从文件名解析的版本号，识别不到为 `unknown` |
| `page` | PDF 页码，HTML 等无页码时为 `unknown` |
| `chunk_id` | 全局 chunk 编号 |
| `source_chunk_id` | `source#chunk_id`，用于稳定定位 |
| `create_time` | 入库时间 |
| `operator` | 入库操作者 |

### 9.2 在线问答流程

```text
用户问题
  -> 查询向量化
  -> Chroma 向量检索
  -> BM25 关键词检索
  -> RRF 融合
  -> Rerank 重排
  -> 拒答阈值判断
  -> 构造带引用编号的 Prompt
  -> LLM 生成回答
  -> 返回答案、引用、上下文和会话记录
```

默认检索参数在 `config_data.py`：

```text
vector_top_k = 10
bm25_top_k = 10
rrf_top_k = 10
rerank_top_k = 5
default_retrieval_mode = "hybrid"
refusal_score_threshold = 0.3
```

BM25 分词策略针对技术文档做了适配：中文按单字处理，英文、数字和 API 符号按词保留，适合匹配 `DataReader`、`DomainParticipantFactory`、`ReliabilityQosPolicy` 等技术名词。

## 10. 引用与原文跳转

回答中的引用编号来自检索结果列表。后端会根据文档类型返回不同信息：

- PDF：展示来源文件、页码、chunk 和片段内容。
- HTML：返回原始 HTML 路径，前端可打开对应 API 文档页面。

引用粒度根据 Rerank 分数分级：

```text
score >= 0.7：fine，显示来源、页码/chunk、摘要
score >= 0.4：medium，显示来源、页码
score < 0.4：coarse，只显示来源
```

这使回答既能保持可读性，又保留必要的证据追溯能力。

## 11. 权限与用户管理

用户和会话数据存储在：

```text
data/auth.sqlite3
```

主要权限：

| 角色/权限 | 能力 |
|---|---|
| 普通用户 | 登录、问答、查看知识库、查看系统状态、管理自己的对话历史 |
| 上传权限 | 上传单文件、批量导入文档 |
| 模型切换权限 | 在系统状态页切换阿里百炼 / Cloudflare 模式 |
| 管理员 | 用户管理、账号禁用、创建用户、分配权限 |

对话历史按用户账号绑定。后端会校验当前用户和 `session_id` 的归属，普通用户不能访问其他用户的会话。

## 12. 主要接口

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 健康检查、模型状态、知识库统计 |
| `/api/auth/login` | POST | 登录 |
| `/api/auth/register` | POST | 注册 |
| `/api/auth/logout` | POST | 退出登录 |
| `/api/auth/me` | GET | 当前用户信息 |
| `/api/config` | GET | 当前系统配置 |
| `/api/admin/users` | GET / POST | 管理员查看和创建用户 |
| `/api/admin/users/{user_id}/permissions` | PATCH | 管理员修改用户权限和启用状态 |
| `/api/models/switch` | POST | 切换模型模式 |
| `/api/chat` | POST | 普通问答 |
| `/api/chat/stream` | POST | SSE 形式问答接口 |
| `/api/retrieve` | POST | 检索调试接口 |
| `/api/documents` | GET | 文档列表 |
| `/api/documents/stats` | GET | 文档统计 |
| `/api/documents/preview` | GET | 文档 chunk 预览 |
| `/api/documents/html` | GET | HTML 原文入口 |
| `/api/html/{file_path}` | GET | HTML 原文及资源访问 |
| `/api/sessions` | GET | 当前用户会话列表 |
| `/api/sessions/{session_id}/history` | GET / DELETE | 获取或清空当前会话历史 |
| `/api/sessions/{session_id}/title` | PATCH | 修改会话标题 |
| `/api/sessions/{session_id}` | DELETE | 删除会话 |
| `/api/upload` | POST | 单文件上传入库 |
| `/api/batch-ingest` | POST | 后端按服务器路径批量导入 |
| `/api/batch-upload` | POST | 前端批量上传文件入库 |
| `/retrieve` | POST | rag-benchmark 兼容检索接口 |
| `/generate` | POST | rag-benchmark 兼容生成接口 |

除健康检查、登录、注册等入口外，大部分接口需要登录 Cookie。

## 13. 评测器接入

项目提供 rag-benchmark 兼容接口：

```text
POST /retrieve
POST /generate
```

评测器可通过 HTTP adapter 接入后端，对以下能力进行评测：

- Chunk Recall@K
- Source Recall@K
- Evidence Recall@K
- MRR
- nDCG@5
- Correct / Partial / Wrong
- Citation Present / Traceable / Supported
- Success Rate
- Latency Avg / P50 / P95
- Overall Score

评测前建议先访问 `/api/health` 确认：

- Ollama `bge-m3` 可用。
- 当前 LLM 和 Rerank 凭据已配置。
- 知识库文档和 chunk 数量符合预期。

## 14. 旧 Streamlit 入口

当前推荐使用 Vue + FastAPI。旧 Streamlit 页面仍保留用于快速调试：

问答页面：

```powershell
cd "D:\project\DDS\DDSRag - v2"
.\.venv\Scripts\streamlit.exe run app_qa.py
```

单文件上传页面：

```powershell
.\.venv\Scripts\streamlit.exe run app_file_uploader.py
```

旧页面不包含完整的登录、管理员、系统状态和 Vue 交互体验。

## 15. 常见问题

### 15.1 后端启动后前端登录显示 fetch failed

先确认后端已经启动并能访问：

```text
http://127.0.0.1:8000/api/health
```

再确认前端请求地址是否指向 `127.0.0.1:8000`。后端启动较慢时，前端可能先显示未连接，等待后端完成加载后刷新即可。

### 15.2 Ollama tokenize refused

错误类似：

```text
Post "http://127.0.0.1:xxxxx/tokenize": connectex refused
```

常见原因：

- Ollama 没启动。
- `bge-m3` 没拉取。
- 大文件 embedding 时 runner 崩溃。

处理：

```powershell
ollama serve
ollama pull bge-m3
```

如果大文件仍失败，可把 `config_data.py` 中的：

```text
embedding_batch_size = 4
```

临时调小为 2 或 1 后重新导入。

### 15.3 百炼或 Cloudflare 报 401 / 403

常见原因：

- `.env` 中 API Key 未配置或配置错误。
- 当前模型没有额度。
- 模型模式切到未配置凭据的平台。

先检查“系统状态”页，再检查 `.env`。

### 15.4 更换 embedding 模型后报维度不一致

Chroma 向量库与 embedding 模型强绑定。更换 embedding 模型后，旧向量库不能直接复用，可能出现：

```text
Collection expecting embedding with dimension X, got Y
```

处理方式是备份旧库后重建知识库，并重新导入文档。

### 15.5 重新导入文件被跳过

项目使用 `md5.text` 记录已导入文件 MD5。相同内容再次导入会被跳过。

如果需要完全重建知识库，应先备份并清理：

```text
chroma_db/
md5.text
```

清理会影响现有知识库，操作前务必备份。

### 15.6 HTML 引用不能跳转到原文

检查 `.env` 或 `config_data.py` 中的 `HTML_SOURCE_ROOT` 是否指向真实 HTML 根目录。例如：

```text
D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc\html
```

知识库中的 HTML `source` 是相对于该目录的路径，路径不一致会导致跳转失败。

## 16. Git 提交建议

建议提交：

```text
backend/
frontend/src/
*.py
requirements.txt
frontend/package.json
frontend/package-lock.json
.env.example
README.md
docs/
```

不建议提交：

```text
.env
.venv/
frontend/node_modules/
frontend/dist/
chroma_db/
data/
chat_history/
uploads/
md5.text
*.sqlite3
*.log
```

如果希望队友拿到已经入库的知识库，不建议直接通过 Git 提交 `chroma_db` 和 `data`。更稳妥的方式是私下共享压缩包或提供统一导入脚本，并说明 embedding 模型和文档版本必须一致。

## 17. 后续优化建议

- 增加更稳定的生产部署方案，例如 Nginx、HTTPS、进程守护和日志监控。
- 对上传大文件增加任务队列和进度状态，避免请求超时。
- 引入 Parent Document Retriever 或相邻 chunk 扩展，改善长文档流程类问题。
- 对 Recall@1 较低的问题做专项分析，继续优化 chunk 切分、RRF 参数和 Rerank 候选数量。
- 增加并发测试、长时间稳定性测试和资源峰值测试。
- 将评测器纳入常规回归流程，每次 RAG 策略调整后保留可比较结果。
