# DDSRag v2 项目说明

本文档记录当前 `DDSRag - v2` 的 RAG 流程、模型配置、入库方式、检索方式和启动方法。

## 1. 当前定位

`DDSRag - v2` 是面向 ZRDDS/DDS 技术文档的本地知识库问答项目。当前版本保留原型项目的 Streamlit 前端和服务层结构，并做了以下升级：

- 本地 Ollama embedding：用于文档入库和查询向量化。
- 阿里百炼 chat：用于最终答案生成。
- 阿里百炼 rerank：用于检索候选片段重排序。
- Chroma 本地向量库：保存文档 chunk 和向量。
- BM25 + 向量混合检索：用于兼顾语义召回和技术关键词召回。
- 批量入库脚本：支持目录递归导入。
- HTML 清洗模块：过滤 Doxygen/Javadoc 噪声页，处理多编码 HTML。
- 引用格式化：回答上下文带 `[n]` 编号和出处。

## 2. 主要文件职责

| 文件 | 作用 |
|---|---|
| `app_qa.py` | Streamlit 问答前端 |
| `app_file_uploader.py` | Streamlit 单文件上传入库前端 |
| `batch_ingest.py` | 命令行批量导入文件/目录 |
| `document_loader.py` | 单文件解析入口，支持 PDF/TXT/CSV/DOCX/HTML |
| `knowledge_base.py` | 文档 metadata 补充、分片、embedding、写入 Chroma |
| `vector_stores.py` | Chroma 向量检索、BM25、RRF、rerank |
| `rag.py` | 检索结果格式化、Prompt、百炼生成、会话历史 |
| `corpus_cleaner.py` | HTML 清洗、噪声过滤、版本和文档类型识别 |
| `citation.py` | 引用格式化 |
| `file_history_store.py` | 本地 JSON 聊天历史 |
| `config_data.py` | 模型、向量库、检索参数配置 |

## 3. 模型配置

当前模型配置在 `config_data.py`：

```python
embedding_provider = "ollama"
embedding_model_name = "bge-m3"
ollama_base_url = "http://localhost:11434"
embedding_batch_size = 4

chat_model_name = "qwen3-max"
rerank_model_name = "qwen3-rerank"
```

含义：

- Embedding 使用本地 Ollama 的 `bge-m3`。
- Chat 生成使用阿里百炼 `qwen3-max`。
- Rerank 使用阿里百炼 `qwen3-rerank`。
- `embedding_batch_size = 4` 表示入库时每批 4 个 chunk 写入 Chroma，避免大文件一次性向量化导致 Ollama runner 崩溃。

运行前需要：

```powershell
ollama serve
ollama pull bge-m3
```

百炼还需要在环境变量或 `.env` 中配置：

```text
DASHSCOPE_API_KEY=你的百炼 API Key
```

## 4. 本地数据位置

当前配置：

```python
collection_name = "rag"
persist_directory = "./chroma_db"
md5_path = "./md5.text"
```

说明：

- `chroma_db/` 保存 Chroma 向量库。
- `md5.text` 记录已导入文件的 MD5，用于避免重复导入。
- 当前 v2 仍使用固定 collection 和固定 Chroma 目录。更换 embedding 模型时，应重建知识库，否则可能出现向量维度不匹配。

## 5. 入库流程

### 5.1 前端单文件上传

启动上传页面：

```powershell
cd "D:\project\DDS\DDSRag - v2"
.\.venv\Scripts\streamlit.exe run app_file_uploader.py
```

支持文件：

```text
pdf / txt / csv / docx / html / htm
```

流程：

```text
app_file_uploader.py
-> DocumentLoaderService.load()
-> KnowledgeBaseService.upload_documents()
-> RecursiveCharacterTextSplitter
-> OllamaEmbeddings(bge-m3)
-> Chroma
```

HTML 文件会走 `corpus_cleaner.load_html()`，支持：

- `utf-8`
- `gbk`
- `gb18030`
- 严格解码失败后的宽容解码兜底

### 5.2 命令行批量导入

预览扫描，不写入知识库：

```powershell
cd "D:\project\DDS\DDSRag - v2"
.\.venv\Scripts\python.exe batch_ingest.py "D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc\html" --dry-run
```

正式导入：

```powershell
.\.venv\Scripts\python.exe batch_ingest.py "D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc\html"
```

导入整个文档目录：

```powershell
.\.venv\Scripts\python.exe batch_ingest.py "D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc"
```

默认会过滤 Doxygen/Javadoc 噪声 HTML，例如：

- `index.html`
- `classes.html`
- `functions.html`
- `files.html`
- `pages.html`
- `*-members.html`
- `*_source.html`
- `search/`
- `static/`

如果确实要把这些噪声页也导入：

```powershell
.\.venv\Scripts\python.exe batch_ingest.py "D:\project\DDS\ZRDDS\ZRDDS-2.5.0\doc\html" --include-noise-html
```

一般不建议使用 `--include-noise-html`，会污染检索结果。

## 6. 入库 metadata

新导入的文档会补充 metadata：

| 字段 | 含义 |
|---|---|
| `source` | 文件名或相对路径 |
| `doc_type` | `pdf`、`c`、`cpp`、`java`、`manual`、`docx`、`csv`、`txt` 等 |
| `version` | 从文件名识别的版本号，识别不到为 `unknown` |
| `page` | PDF 页码；无页码则为 `unknown` |
| `chunk_id` | 单次文件内 chunk 编号 |
| `source_chunk_id` | `source#chunk_id`，用于稳定定位 |
| `create_time` | 入库时间 |
| `operator` | 当前固定为 `小虎` |

注意：metadata 升级只影响新导入数据。旧库里已存在的 chunk 不会自动补齐 metadata。

## 7. 检索流程

默认检索模式在 `config_data.py`：

```python
default_retrieval_mode = "hybrid"
```

### 7.1 Hybrid 混合检索

默认流程：

```text
用户问题
-> Ollama bge-m3 查询向量
-> Chroma 向量召回 top_k
-> BM25 关键词召回 top_k
-> RRF 融合去重
-> 百炼 qwen3-rerank 重排序
-> top 文档片段进入 Prompt
-> 百炼 qwen3-max 生成答案
```

BM25 分词策略在 `vector_stores.py`：

```text
中文按单字
英文 / 数字 / API 符号按词
```

这比纯 `jieba` 更适合 DDS 技术文档，例如：

- `DDS::DataReader`
- `DomainParticipantFactory`
- `qos_profile`
- `ReliabilityQosPolicy`

### 7.2 Vector 纯向量检索

可以把 `config_data.py` 改为：

```python
default_retrieval_mode = "vector"
```

纯向量流程：

```text
用户问题
-> Ollama bge-m3 查询向量
-> Chroma similarity_search
-> 百炼 qwen3-rerank 重排序
-> 百炼 qwen3-max 生成答案
```

## 8. 命令行检索对比

可以直接用 `vector_stores.py` 对比检索效果。

纯向量：

```powershell
.\.venv\Scripts\python.exe vector_stores.py --vector "DataReader 如何读取数据"
```

混合检索：

```powershell
.\.venv\Scripts\python.exe vector_stores.py --hybrid "DataReader 如何读取数据"
```

注意：这两个命令都会调用 rerank，因此需要百炼 `qwen3-rerank` 可用。

## 9. 问答启动方式

启动问答前端：

```powershell
cd "D:\project\DDS\DDSRag - v2"
.\.venv\Scripts\streamlit.exe run app_qa.py
```

问答流程：

```text
app_qa.py
-> RagService.chain.stream()
-> VectorStoreService.search()
-> format_document_block()
-> ChatPromptTemplate
-> ChatTongyi(qwen3-max)
-> Streamlit 流式输出
```

当前 Prompt 要求：

- 仅基于参考资料回答。
- 不编造资料之外的内容。
- 在相关句末使用 `[n]` 标注引用编号。
- 资料不足时明确说明资料不足。

## 10. 引用格式

引用格式由 `citation.py` 生成。

PDF/PPTX 示例：

```text
[1] 出处: ZRDDS用户手册.pdf | p.12 | v2.0
```

HTML/API 示例：

```text
[2] 出处: cpp\class_d_d_s_1_1_data_reader.html | chunk 302
```

回答中应使用：

```text
DataReader 用于读取订阅到的数据 [2]。
```

## 11. 常见问题

### 11.1 Ollama tokenize refused

错误类似：

```text
Post "http://127.0.0.1:xxxxx/tokenize": connectex refused
```

常见原因：

- Ollama 没启动。
- `bge-m3` 模型没拉取。
- 单次 embedding 批量太大，runner 崩溃。

处理：

```powershell
ollama serve
ollama pull bge-m3
```

如果大文件仍失败，可以在 `config_data.py` 中把：

```python
embedding_batch_size = 4
```

调成：

```python
embedding_batch_size = 2
```

或：

```python
embedding_batch_size = 1
```

### 11.2 百炼 403 Free quota exhausted

错误类似：

```text
AllocationQuota.FreeTierOnly
Free quota exhausted
```

说明当前调用的百炼模型没有可用额度。v2 中百炼仍用于：

- `qwen3-rerank`
- `qwen3-max`

Embedding 不再使用百炼，已经改为 Ollama。

### 11.3 重新导入为什么被跳过

因为 `md5.text` 中已有该文件的 MD5。若要让同一批文件重新入库，需要先处理旧 Chroma 数据和 `md5.text`。这会影响现有知识库，操作前应先备份。

### 11.4 更换 embedding 模型后怎么办

更换 embedding 模型后，必须重建 Chroma 知识库。不同 embedding 模型的向量维度可能不同，混用会导致：

```text
Collection expecting embedding with dimension X, got Y
```

当前 v2 仍使用固定目录 `chroma_db`，所以换模型前应明确备份和重建。

## 12. 当前限制

- 当前没有专门的知识库清单查询接口。
- 当前没有上下文相邻 chunk 扩展。
- 当前没有针对“某文档整体总结/流程归纳”的文档级检索策略。
- 当前没有接入 `rag-benchmark` 的 v2 专用 adapter。
- 当前 `chunk_id` 是单文件内编号，跨文件稳定定位依赖 `source_chunk_id`。
- 旧数据 metadata 不会自动迁移，需要重新导入或专门迁移脚本。

## 13. 建议后续升级

建议按以下顺序继续：

1. 空检索保护，避免无资料时仍调用大模型。
2. 知识库清单查询，直接列出已入库文档。
3. 上下文相邻 chunk 扩展。
4. 模型和向量库目录绑定，避免换 embedding 后维度冲突。
5. 对接 `rag-benchmark`，先做 retrieval-only 评测。
