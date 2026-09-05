# DDSRag

基于大语言模型的 DDS 技术文档可信问答系统。

本项目面向 DDS 产品的技术文档问答场景，通过文档解析、文本切分、向量检索、BM25 关键词检索、RRF 混合检索、Reranker 重排序以及大语言模型生成，实现基于知识库的技术问答。

项目当前版本重点优化了 **Hybrid Retrieval（混合检索）**，结合语义检索与关键词检索，提高技术文档场景下的检索准确性。

---

## 1. 项目简介

传统的大语言模型无法直接获得项目内部 DDS 产品文档中的最新、专有知识，因此直接让 LLM 回答容易出现知识缺失和幻觉问题。

本项目采用 RAG（Retrieval-Augmented Generation，检索增强生成）架构：

```text
用户问题
   │
   ▼
查询问题
   │
   ├───────────────┐
   ▼               ▼
向量检索          BM25
   │               │
   └───────┬───────┘
           ▼
       RRF 融合
           │
           ▼
       Reranker
           │
           ▼
      Top-K 文档
           │
           ▼
       Prompt
           │
           ▼
      大语言模型
           │
           ▼
        最终回答
```

相比单一向量检索，本项目进一步加入 BM25 和 RRF，使系统同时利用：

* **语义信息**
* **关键词信息**
* **文档排名信息**
* **Reranker 精排能力**

从而提高 DDS 技术文档场景下的检索效果。

---

## 2. 当前功能

### 2.1 文档知识库

支持将技术文档解析为 LangChain `Document`，并进行文本切分。

主要流程：

```text
原始文档
   ↓
Document
   ↓
Metadata
   ↓
RecursiveCharacterTextSplitter
   ↓
Text Chunks
   ↓
Chroma
```

文档 Chunk 会保存包括来源、创建时间等 Metadata。

---

### 2.2 Chroma 向量检索

使用 DashScope Embedding 模型将文本转换为向量，并存储到 Chroma。

用户提出问题后：

```text
Query
 ↓
Embedding
 ↓
Chroma Similarity Search
 ↓
Top-K Documents
```

向量检索主要用于发现与用户问题语义相近的内容。

---

### 2.3 BM25 关键词检索

项目同时实现 BM25 检索。

中文文本在进入 BM25 前使用 `jieba` 进行分词：

```text
用户问题
   ↓
jieba 分词
   ↓
BM25
   ↓
Top-K Documents
```

BM25 对技术名词、配置项、函数名、宏定义等关键词具有较好的匹配能力。

例如：

```text
ZRDDSCppzd.lib
ZRDDSCppz.lib
_ZRDDSCPPINTERFACE
ZRDDS_HOME
```

这类技术关键词并不一定能够完全依赖语义检索命中，因此 BM25 可以作为向量检索的重要补充。

---

### 2.4 RRF 混合检索

Vector Search 和 BM25 的评分体系不同，因此没有直接对两个检索器的原始分数进行相加。

项目使用 Reciprocal Rank Fusion（RRF）进行结果融合。

核心公式：

```text
RRF(d) = Σ 1 / (k + rank(d))
```

其中：

* `d`：文档
* `rank(d)`：文档在某个检索器中的排名
* `k`：RRF 参数

当前检索流程：

```text
Vector Top-K ──┐
               │
               ▼
              RRF
               ▲
               │
BM25 Top-K ────┘
```

这样可以综合利用两种检索方式的排名信息。

---

### 2.5 DashScope Reranker

RRF 得到候选文档后，进一步使用 DashScope Reranker 对候选文档进行重新排序。

流程：

```text
Hybrid Retrieval
       ↓
RRF Candidate Documents
       ↓
DashScope Reranker
       ↓
Relevance Score
       ↓
Final Top-K
```

Reranker 接收：

```text
Query
+
Candidate Documents
```

并重新计算查询与候选文档之间的相关性。

当前使用：

```text
qwen3-rerank
```

---

### 2.6 对话历史

系统支持多轮对话。

用户可以连续进行：

```text
用户：简单介绍一下 ZRDDS

AI：……

用户：它的 QoS 策略有哪些？

AI：……

用户：那 Reliability 是干什么的？

AI：……
```

系统通过 Conversation History 将历史消息传递给 LLM，使模型能够理解当前问题的上下文。

---

### 2.7 Streamlit Web UI

项目使用 Streamlit 提供简单的 Web 问答界面。

主要功能：

* 用户输入问题
* AI 流式回答
* 多轮对话
* 知识库 RAG 问答

启动后可以通过浏览器访问 Streamlit 页面。

---

## 3. 技术架构

```text
                    ┌────────────────────┐
                    │     Streamlit      │
                    │     Web UI         │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │     RagService     │
                    └─────────┬──────────┘
                              │
                              ▼
                     Hybrid Retrieval
                              │
               ┌──────────────┴──────────────┐
               │                             │
               ▼                             ▼
        Vector Retrieval                 BM25
               │                             │
               └──────────────┬──────────────┘
                              ▼
                         RRF Fusion
                              │
                              ▼
                         Reranker
                              │
                              ▼
                    Retrieved Documents
                              │
                              ▼
                         Prompt
                              │
                              ▼
                       DashScope LLM
                              │
                              ▼
                         Final Answer
```

---

## 4. 项目结构

```text
DDSRag/
│
├── app_qa.py                  # Streamlit 问答前端
│
├── rag.py                     # RAG 核心流程
│
├── vector_stores.py           # 检索基础设施
│   ├── Vector Search
│   ├── BM25
│   ├── RRF
│   └── Reranker
│
├── knowledge_base.py          # 知识库构建
│   ├── 文档处理
│   ├── Metadata
│   ├── Chunk
│   └── Chroma
│
├── file_history_store.py      # 对话历史存储
│
├── config_data.py             # 项目配置
│
├── requirements.txt           # Python 依赖
│
├── .env.example               # 环境变量模板
│
├── .gitignore                 # Git 忽略配置
│
└── README.md
```

---

## 5. 环境要求

建议环境：

```text
Python 3.x
Windows / Linux
```

项目主要依赖：

```text
LangChain
LangChain Chroma
Chroma
DashScope
jieba
Streamlit
BM25
```

---

## 6. 安装

### 6.1 克隆项目

```bash
git clone https://github.com/starkflynn8-collab/rag-knowledge-base.git
cd rag-knowledge-base
```

---

### 6.2 创建虚拟环境

Windows：

```powershell
python -m venv .venv
```

激活：

```powershell
.\.venv\Scripts\activate
```

---

### 6.3 安装依赖

```powershell
pip install -r requirements.txt
```

如果项目环境中缺少 Chroma：

```powershell
pip install -U langchain-chroma
```

---

## 7. 配置 API Key

项目使用阿里云 DashScope API。

首先复制：

```text
.env.example
```

创建：

```text
.env
```

然后填写 API Key：

```text
DASHSCOPE_API_KEY=your_api_key
```

注意：

> `.env` 仅用于本地开发，不应该上传到 GitHub。

项目已经通过 `.gitignore` 忽略 `.env`。

---

## 8. 启动项目

### 8.1 启动 Streamlit

推荐使用当前项目虚拟环境中的 Python 启动：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app_qa.py
```

不要直接依赖系统环境中的：

```powershell
streamlit run app_qa.py
```

这样可以避免 Streamlit 使用错误 Python 环境导致依赖缺失。

---

### 8.2 单独测试 RAG

可以直接运行：

```powershell
.\.venv\Scripts\python.exe rag.py
```

用于测试：

```text
Vector Retrieval
BM25 Retrieval
RRF Fusion
Reranker
LLM Generation
```

---

### 8.3 单独测试 Hybrid Retrieval

运行：

```powershell
.\.venv\Scripts\python.exe vector_stores.py
```

可以观察：

```text
========== Vector Retrieval ==========

========== BM25 Retrieval ==========

========== RRF Fusion ==========

========== Reranker ==========

========== Hybrid Search Finished ==========
```

方便调试检索效果。

---

## 9. RAG 检索流程示例

例如用户输入：

```text
简单介绍下基于 C++ 构建 ZRDDS 的方式
```

系统分别执行：

### Vector Retrieval

获取语义相关文档。

### BM25 Retrieval

根据：

```text
C++
ZRDDS
构建
```

等关键词进行检索。

### RRF

将两套检索结果进行融合。

### Reranker

对 RRF 得到的候选文档重新计算相关性。

最终将排序靠前的文档交给 LLM。

---

## 10. 当前版本特点

当前版本的核心检索架构：

```text
Dense Retrieval
      +
Sparse Retrieval
      ↓
     RRF
      ↓
  Reranker
      ↓
     LLM
```

即：

```text
Vector Search
+
BM25
+
RRF
+
Qwen Reranker
+
LLM
```

该架构相比单一 Vector Search 能够同时利用：

* 语义相似度
* 关键词匹配
* 多路检索结果
* Cross-Encoder / Reranker 精排

特别适合 DDS 技术文档、API 文档、配置文档、故障排查文档等技术资料场景。

---

## 11. 后续规划

项目后续计划继续向可信 RAG 系统升级：

```text
当前版本
   │
   ├── Hybrid Retrieval
   ├── RRF
   └── Reranker
        │
        ▼
下一阶段
   │
   ├── Metadata / 文档结构增强
   ├── Parent-Child Chunk
   ├── Answer Citation
   ├── RAG 拒答机制
   ├── Evaluation 数据集
   ├── Recall@K / MRR 等指标
   ├── Retrieval 对比实验
   └── Query Rewrite
```

最终目标：

```text
文档知识库
     ↓
智能检索
     ↓
证据筛选
     ↓
可信生成
     ↓
来源引用
     ↓
可评估 RAG 系统
```

---

## 12. 项目定位

本项目本质上是一个面向 DDS 技术文档的：

> **Hybrid Retrieval + Reranker + LLM 的可信 RAG 问答系统**

重点不只是调用大语言模型，而是围绕：

```text
Knowledge Base
Retrieval
Ranking
Generation
Evaluation
```

构建完整的 RAG Pipeline。

---


