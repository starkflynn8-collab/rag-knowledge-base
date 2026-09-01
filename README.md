# RAG Knowledge Base

基于 **LangChain、Chroma、阿里云百炼 Qwen 和 DashScope Embedding** 构建的 RAG（Retrieval-Augmented Generation）知识库问答系统。

项目实现了从**文档加载、文本分块、向量化、向量数据库存储、相似度检索到大模型生成回答**的完整 RAG 流程，并支持多轮对话和本地聊天历史持久化。

---

## 1. 项目简介

传统的大语言模型只能依赖自身训练数据回答问题，无法直接获取用户提供的私有知识。

本项目通过 RAG 技术，将用户提供的知识文档构建为本地向量知识库。

用户提问后：

```text
用户问题
    ↓
问题向量化
    ↓
Chroma 向量数据库
    ↓
相似度检索
    ↓
Top-K 相关文档片段
    ↓
结合对话历史构造 Prompt
    ↓
Qwen 大模型
    ↓
生成回答
```

从而实现基于外部知识库的智能问答。

---

## 2. 当前功能

### 知识库构建

* 文档内容读取
* 文本分块
* RecursiveCharacterTextSplitter
* DashScope Embedding 向量化
* Chroma 本地向量数据库
* MD5 内容去重
* 文档 Metadata 保存

### 问答系统

* 基于 Chroma 的向量相似度检索
* Top-K 文档召回
* RAG Prompt 构建
* Qwen 大模型生成
* 多轮对话
* 对话历史持久化
* Streamlit Web 界面
* 流式输出 AI 回答

### 文件上传

知识库支持通过 Streamlit 页面上传文档。

当前项目可以扩展支持：

* TXT
* PDF
* CSV
* DOCX
* HTML

不同格式的文档经过对应 Loader 读取后，统一转换为 LangChain `Document`，再进入后续的文本分块和向量化流程。

---

## 3. RAG 核心流程

### 3.1 构建索引

```text
文档
 ↓
Document Loader
 ↓
LangChain Document
 ↓
文本分块
 ↓
Chunk
 ↓
DashScope Embedding
 ↓
向量
 ↓
Chroma
```

其中：

**数据加载**

将 PDF、TXT、CSV、DOCX、HTML 等文件转换为 LangChain `Document`。

**文本分块**

使用：

```text
RecursiveCharacterTextSplitter
```

将较长的文档拆分成适合检索的文本片段。

**文本嵌入**

使用阿里云百炼：

```text
text-embedding-v4
```

将文本转换为向量。

**创建索引**

将文本、向量和 Metadata 保存到 Chroma 本地向量数据库。

---

### 3.2 检索

用户提出问题后：

```text
用户问题
 ↓
DashScope Embedding
 ↓
Query Vector
 ↓
Chroma
 ↓
向量相似度计算
 ↓
Top-K
 ↓
相关 Document
```

当前版本采用：

> **纯向量召回（Dense Vector Retrieval）**

即通过文本 Embedding 后的向量相似度进行相关文档检索。

当前版本**尚未实现 BM25 + 向量检索的混合检索**。

---

### 3.3 生成

检索得到相关知识后，将：

```text
参考资料
+
历史对话
+
当前用户问题
```

组合成 Prompt：

```text
System:
以提供的已知参考资料为主，
简洁和专业地回答用户问题。

参考资料：
{context}

历史对话：
{history}

User:
请回答用户提问：
{input}
```

随后交给 Qwen 大模型生成最终回答。

---

## 4. 项目结构

```text
rag-knowledge-base/
│
├── app_qa.py                  # Streamlit 智能问答页面
├── app_file_upload.py         # Streamlit 知识库文件上传页面
│
├── rag.py                     # RAG 核心问答流程
├── knowledge_base.py          # 知识库构建
├── vector_stores.py           # Chroma 向量数据库及 Retriever
├── file_history_store.py      # 本地聊天历史持久化
├── document_loader.py         # 多格式文档加载
│
├── config_data.py             # 项目配置
│
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量配置模板
├── .gitignore                 # Git 忽略文件
└── README.md                  # 项目说明
```

---

## 5. 核心模块说明

### `knowledge_base.py`

负责知识库构建。

主要流程：

```text
文件内容
 ↓
MD5 检查
 ↓
判断是否重复
 ↓
文本分块
 ↓
添加 Metadata
 ↓
Embedding
 ↓
Chroma
 ↓
保存 MD5
```

其中使用 MD5 对文档内容进行去重，避免相同内容被重复加入知识库。

---

### `vector_stores.py`

负责访问 Chroma 向量数据库，并向 RAG 系统提供 Retriever。

核心结构：

```text
VectorStoreService
       ↓
     Chroma
       ↓
   Retriever
```

当前版本主要提供基于向量相似度的检索。

---

### `rag.py`

负责整个 RAG 问答链。

核心流程：

```text
用户问题
 ↓
Retriever
 ↓
相关 Document
 ↓
Document 格式化
 ↓
Context
 ↓
Prompt
 ↓
历史消息
 ↓
Qwen
 ↓
回答
```

同时通过：

```text
RunnableWithMessageHistory
```

实现多轮对话。

---

### `file_history_store.py`

负责保存聊天历史。

聊天记录以 JSON 形式保存在本地：

```text
chat_history/
```

不同的 `session_id` 对应不同的聊天历史。

```text
session_id
    ↓
本地文件
    ↓
历史消息
```

---

### `app_qa.py`

提供用户问答界面。

基于 Streamlit 实现：

```text
用户输入
 ↓
RagService
 ↓
RAG Chain
 ↓
流式返回
 ↓
Streamlit 展示
```

---

### `app_file_upload.py`

提供知识库更新界面。

用户上传文档后：

```text
上传文件
 ↓
读取文件
 ↓
Document Loader
 ↓
KnowledgeBaseService
 ↓
文本分块
 ↓
Embedding
 ↓
Chroma
```

---

## 6. 技术栈

| 技术                             | 用途         |
| ------------------------------ | ---------- |
| Python                         | 项目开发语言     |
| LangChain                      | RAG 应用开发框架 |
| Qwen                           | 大语言模型      |
| DashScope                      | 阿里云百炼模型服务  |
| text-embedding-v4              | 文本向量化      |
| Chroma                         | 向量数据库      |
| Streamlit                      | Web UI     |
| RecursiveCharacterTextSplitter | 文本分块       |
| JSON                           | 聊天历史存储     |
| Git / GitHub                   | 项目版本管理     |

---

## 7. 环境要求

建议使用：

```text
Python 3.10+
```

推荐创建虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

---

## 8. 安装依赖

克隆项目：

```bash
git clone https://github.com/你的用户名/rag-knowledge-base.git
```

进入项目目录：

```bash
cd rag-knowledge-base
```

安装依赖：

```bash
pip install -r requirements.txt
```

---

## 9. API Key 配置

本项目使用**阿里云百炼**提供的 Qwen 大模型和 DashScope Embedding 服务。

运行项目之前，需要配置自己的：

```text
DASHSCOPE_API_KEY
```

### 方法一：使用 `.env`

复制：

```text
.env.example
```

创建：

```text
.env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

然后修改 `.env`：

```env
DASHSCOPE_API_KEY=你的API_Key
```

例如：

```env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 方法二：配置系统环境变量

Windows PowerShell：

```powershell
$env:DASHSCOPE_API_KEY="你的API_Key"
```

Linux / macOS：

```bash
export DASHSCOPE_API_KEY="你的API_Key"
```

**请勿将真实 API Key 提交到 GitHub。**

项目中的：

```text
.env
```

已经加入 `.gitignore`。

GitHub 中仅保留：

```text
.env.example
```

作为配置模板。

---

## 10. 启动问答系统

运行：

```bash
streamlit run app_qa.py
```

启动后打开 Streamlit 提供的本地地址。

进入智能客服页面后即可进行问答。

---

## 11. 更新知识库

运行：

```bash
streamlit run app_file_upload.py
```

进入知识库更新页面。

上传文档后，系统会：

```text
读取文件
 ↓
文档解析
 ↓
文本分块
 ↓
Embedding
 ↓
保存到 Chroma
```

之后用户提问时，Retriever 可以从知识库中召回相关内容。

---

## 12. 数据存储

项目默认使用本地目录保存相关数据。

例如：

```text
chroma_db/
```

用于保存 Chroma 向量数据库。

```text
chat_history/
```

用于保存本地聊天历史。

这些运行时数据默认不会上传到 GitHub。

---

## 13. 安全说明

本项目使用 API Key 调用阿里云百炼服务。

请注意：

```text
❌ 不要把 API Key 写死在 Python 源代码中
❌ 不要将 .env 上传到 GitHub
❌ 不要在 README 中填写真实 API Key
❌ 不要将包含 API Key 的配置文件提交到 Git
```

推荐：

```text
.env
    ↓
DASHSCOPE_API_KEY
    ↓
本地环境变量
    ↓
ChatTongyi / DashScopeEmbeddings
```

GitHub 仅保存：

```text
.env.example
```

---

## 14. 当前 RAG 架构

```text
                    ┌──────────────────┐
                    │   用户上传文档    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │  Document Loader │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │    文本分块       │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ DashScope Embed  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │      Chroma      │
                    └──────────────────┘


用户问题
    ↓
Embedding
    ↓
Chroma Vector Search
    ↓
Top-K Documents
    ↓
Context
    +
History
    +
Question
    ↓
Prompt
    ↓
Qwen
    ↓
最终回答
```

---

## 15. 后续升级计划

项目后续计划进一步优化 RAG 检索效果：

```text
当前
纯向量召回
    ↓
混合检索
    ↓
Vector Search + BM25
    ↓
RRF 结果融合
    ↓
Reranker
    ↓
Metadata / 来源引用
    ↓
RAG 检索效果评估
```

计划实现：

* [ ] 支持更多文档格式
* [ ] BM25 关键词检索
* [ ] 向量检索 + BM25 混合检索
* [ ] RRF 召回结果融合
* [ ] Reranker 重排序
* [ ] 文档来源引用
* [ ] 检索效果评估
* [ ] RAG 参数优化
* [ ] 更完善的知识库管理

---

## 16. 项目定位

本项目主要用于学习和实践：

```text
RAG
│
├── Document Loading
├── Text Splitting
├── Embedding
├── Vector Database
├── Dense Retrieval
├── Prompt Engineering
├── LLM Generation
├── Conversation Memory
└── Streamlit Application
```

后续将进一步探索：

```text
Hybrid Retrieval
Reranking
RAG Evaluation
```

以提高复杂知识库场景下的检索准确率和回答可靠性。
