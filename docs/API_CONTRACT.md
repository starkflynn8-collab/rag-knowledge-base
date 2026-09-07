# DDSRag v2 API Contract

本文档定义 `DDSRag - v2` 升级为 Vue + FastAPI 架构时的接口契约。目标是让前端、后端、RAG 优化、模型实验、评测部署可以并行开发。

## 1. 总体约定

### 1.1 架构边界

```text
Vue 前端
  -> FastAPI API 层
      -> DDSRag v2 服务层
          -> DocumentLoaderService
          -> KnowledgeBaseService
          -> VectorStoreService
          -> RagService
          -> Chroma
          -> Ollama embedding
          -> 百炼 LLM / rerank
```

约定：

- Vue 不直接访问 Chroma。
- Vue 不直接调用 Ollama。
- Vue 不直接调用百炼。
- FastAPI 是唯一后端入口。
- RAG 内部可以持续优化，但必须保持本文档定义的 API 请求和响应结构稳定。
- 后端返回给前端的路径、source、citation 都应来自知识库 metadata，不由前端拼接。

### 1.2 Base URL

本地开发默认：

```text
http://127.0.0.1:8000
```

生产或测试环境通过前端环境变量配置：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### 1.3 Content Type

普通 JSON 接口：

```http
Content-Type: application/json
```

文件上传接口：

```http
Content-Type: multipart/form-data
```

流式问答接口建议使用：

```http
Content-Type: text/event-stream
```

### 1.4 通用响应结构

成功响应：

```json
{
  "success": true,
  "data": {},
  "message": "ok",
  "request_id": "req_20260906_153000_abcd"
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "OLLAMA_UNAVAILABLE",
    "message": "Ollama 服务不可用，请确认 ollama serve 已启动",
    "detail": "connect refused: http://localhost:11434"
  },
  "request_id": "req_20260906_153000_abcd"
}
```

说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---:|---:|---|
| `success` | boolean | 是 | 请求是否成功 |
| `data` | object/array/null | 成功时是 | 业务数据 |
| `message` | string | 否 | 成功提示 |
| `error` | object | 失败时是 | 错误信息 |
| `request_id` | string | 是 | 请求追踪 ID |

### 1.5 通用错误码

| 错误码 | HTTP 状态 | 场景 | 前端建议 |
|---|---:|---|---|
| `BAD_REQUEST` | 400 | 请求参数错误 | 提示用户检查输入 |
| `FILE_TYPE_UNSUPPORTED` | 400 | 文件类型不支持 | 提示支持类型 |
| `FILE_EMPTY` | 400 | 文件无有效文本 | 提示换文件或检查内容 |
| `PATH_NOT_FOUND` | 404 | 批量导入路径不存在 | 提示路径不存在 |
| `KB_EMPTY` | 409 | 知识库为空 | 引导用户先导入文档 |
| `OLLAMA_UNAVAILABLE` | 503 | Ollama 未启动或模型不可用 | 提示启动 Ollama |
| `EMBEDDING_FAILED` | 500 | embedding 失败 | 展示 detail，建议降低 batch size |
| `RERANK_FAILED` | 502 | rerank 调用失败 | 提示百炼 rerank 异常 |
| `LLM_FAILED` | 502 | LLM 生成失败 | 提示百炼模型异常或额度不足 |
| `DASHSCOPE_QUOTA_EXHAUSTED` | 402 | 百炼额度不足 | 提示更换 API key 或充值 |
| `INTERNAL_ERROR` | 500 | 未知错误 | 展示通用错误和 request_id |

## 2. 数据模型

### 2.1 DocumentSummary

用于知识库文档列表。

```json
{
  "source": "ZRDDS用户手册.pdf",
  "doc_type": "pdf",
  "version": "2.0",
  "chunk_count": 123,
  "page_count": 56,
  "create_time": "2026-09-06 15:30:00",
  "operator": "小虎"
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---:|---|
| `source` | string | 文件名或相对路径 |
| `doc_type` | string | `pdf/c/cpp/java/manual/docx/csv/txt/unknown` |
| `version` | string | 版本号，未知为 `unknown` |
| `chunk_count` | number | 该 source 下 chunk 数 |
| `page_count` | number/null | PDF 页数或估算页数 |
| `create_time` | string/null | 入库时间 |
| `operator` | string/null | 操作人 |

### 2.2 RetrievedDocument

用于问答引用和调试面板。

```json
{
  "index": 1,
  "source": "ZRDDS故障排查指南.pdf",
  "doc_type": "pdf",
  "version": "unknown",
  "page": "12",
  "chunk_id": 8,
  "source_chunk_id": "ZRDDS故障排查指南.pdf#8",
  "citation": "ZRDDS故障排查指南.pdf | p.12",
  "score": 0.8132,
  "text": "用于回答的完整片段文本",
  "snippet": "用于前端列表展示的片段摘要..."
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---:|---|
| `index` | number | 引用编号，对应答案中的 `[n]` |
| `source` | string | 来源文件 |
| `doc_type` | string | 文档类型 |
| `version` | string | 版本 |
| `page` | string/null | 页码或 `unknown` |
| `chunk_id` | string/number/null | chunk 编号 |
| `source_chunk_id` | string/null | 稳定 chunk 定位 ID |
| `citation` | string | 格式化引用 |
| `score` | number/null | 检索或 rerank 分数 |
| `text` | string | 完整片段 |
| `snippet` | string | 摘要，用于前端展示 |

### 2.3 ChatMessage

```json
{
  "role": "user",
  "content": "ZRDDS 如何排查通信失败？",
  "created_at": "2026-09-06T15:30:00+08:00"
}
```

`role` 可选：

```text
user / assistant / system
```

### 2.4 IngestResult

```json
{
  "source": "cpp\\class_d_d_s_1_1_data_reader.html",
  "status": "success",
  "message": "[成功]内容已成功载入向量库，共生成 3 个文本块，按每批 4 个文本块写入",
  "chunk_count": 3,
  "skipped_reason": null
}
```

`status` 可选：

```text
success / skipped / failed
```

## 3. 系统状态接口

### 3.1 健康检查

```http
GET /api/health
```

用途：

- 前端首页判断后端是否可用。
- 部署脚本判断服务是否启动。
- 显示当前模型和知识库状态。

成功响应：

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "app": "DDSRag v2",
    "api_version": "1.0",
    "embedding": {
      "provider": "ollama",
      "model": "bge-m3",
      "base_url": "http://localhost:11434",
      "available": true
    },
    "llm": {
      "provider": "dashscope",
      "model": "qwen3-max",
      "available": true
    },
    "rerank": {
      "provider": "dashscope",
      "model": "qwen3-rerank",
      "available": true
    },
    "retrieval": {
      "default_mode": "hybrid",
      "vector_top_k": 10,
      "bm25_top_k": 10,
      "rrf_top_k": 10,
      "rerank_top_k": 5
    },
    "knowledge_base": {
      "collection": "rag",
      "persist_directory": "./chroma_db",
      "document_count": 10,
      "chunk_count": 3456
    }
  },
  "message": "ok",
  "request_id": "req_xxx"
}
```

说明：

- `available` 可以第一版先做静态判断，后续再做真实探测。
- Ollama 探测可以访问 `/api/tags` 或尝试一次短文本 embedding。
- 百炼可用性不要在每次 health 都真实调用大模型，避免耗额度；可以只检查 `DASHSCOPE_API_KEY` 是否存在。

## 4. 问答接口

### 4.1 非流式问答

```http
POST /api/chat
```

请求：

```json
{
  "question": "ZRDDS 如何排查通信失败？",
  "session_id": "user_001",
  "retrieval_mode": "hybrid",
  "top_k": 5,
  "return_context": true
}
```

字段说明：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---:|---:|---|---|
| `question` | string | 是 | 无 | 用户问题 |
| `session_id` | string | 否 | `user_001` | 会话 ID |
| `retrieval_mode` | string | 否 | 配置默认值 | `hybrid` 或 `vector` |
| `top_k` | number | 否 | `rerank_top_k` | 返回给前端的引用数量 |
| `return_context` | boolean | 否 | `true` | 是否返回检索片段 |

成功响应：

```json
{
  "success": true,
  "data": {
    "answer": "排查通信失败时，建议先确认网络连通性，再检查 QoS、Domain ID、Topic 和数据类型是否匹配，并结合日志与抓包分析问题 [1][2]。",
    "session_id": "user_001",
    "retrieval_mode": "hybrid",
    "citations": [
      {
        "index": 1,
        "source": "ZRDDS故障排查指南.pdf",
        "doc_type": "pdf",
        "version": "unknown",
        "page": "12",
        "chunk_id": 8,
        "source_chunk_id": "ZRDDS故障排查指南.pdf#8",
        "citation": "ZRDDS故障排查指南.pdf | p.12",
        "score": null,
        "snippet": "使用 ping 命令查看相关节点网络是否联通..."
      }
    ],
    "usage": {
      "prompt_tokens": null,
      "completion_tokens": null,
      "total_tokens": null
    },
    "latency_ms": 2380
  },
  "message": "ok",
  "request_id": "req_xxx"
}
```

约定：

- 如果 `return_context=false`，`citations` 仍返回，但可以不返回完整 `text`。
- 回答中的 `[n]` 必须对应 `citations[index=n]`。
- 后端负责把检索到的 LangChain `Document` 转成 `RetrievedDocument`。

### 4.2 流式问答

```http
POST /api/chat/stream
```

请求同 `/api/chat`。

响应类型：

```http
Content-Type: text/event-stream
```

SSE 事件示例：

```text
event: retrieval
data: {"retrieval_mode":"hybrid","documents":[{"index":1,"source":"ZRDDS用户手册.pdf","citation":"ZRDDS用户手册.pdf | p.12"}]}

event: token
data: {"text":"ZRDDS"}

event: token
data: {"text":" 排故"}

event: done
data: {"answer":"ZRDDS 排故...","citations":[{"index":1,"source":"ZRDDS用户手册.pdf"}],"latency_ms":2380}
```

错误事件：

```text
event: error
data: {"code":"LLM_FAILED","message":"百炼模型调用失败","detail":"Free quota exhausted"}
```

前端约定：

- 收到 `retrieval` 事件后，可以先展示“已命中文档来源”。
- 收到 `token` 事件后，增量拼接答案。
- 收到 `done` 事件后，用完整 answer 和 citations 覆盖最终状态。
- 收到 `error` 事件后，停止流式输出并展示错误。

### 4.3 只检索不生成

```http
POST /api/retrieve
```

用途：

- 前端调试面板。
- rag-benchmark retrieval-only 评测。
- 对比 `vector` 与 `hybrid`。

请求：

```json
{
  "query": "ReliabilityQosPolicy 有什么作用？",
  "retrieval_mode": "hybrid",
  "k": 10,
  "rerank": true
}
```

成功响应：

```json
{
  "success": true,
  "data": {
    "query": "ReliabilityQosPolicy 有什么作用？",
    "retrieval_mode": "hybrid",
    "documents": [
      {
        "index": 1,
        "source": "cpp\\struct_d_d_s___reliability_qos_policy.html",
        "doc_type": "cpp",
        "version": "unknown",
        "page": "unknown",
        "chunk_id": 0,
        "source_chunk_id": "cpp\\struct_d_d_s___reliability_qos_policy.html#0",
        "citation": "cpp\\struct_d_d_s___reliability_qos_policy.html | chunk 0",
        "score": null,
        "text": "完整检索片段...",
        "snippet": "摘要..."
      }
    ],
    "latency_ms": 890
  },
  "message": "ok",
  "request_id": "req_xxx"
}
```

说明：

- 第一版可直接调用 `VectorStoreService.search(query, mode=retrieval_mode)`。
- 如需实现 `rerank=false`，后端可以调用较底层的向量/BM25函数；如果暂不支持，应返回 `BAD_REQUEST` 或忽略并在响应中声明实际使用了 rerank。

## 5. 知识库接口

### 5.1 获取知识库文档清单

```http
GET /api/documents
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---:|---:|---|
| `doc_type` | string | 否 | 按类型过滤，如 `pdf/cpp/java` |
| `keyword` | string | 否 | 按 source 模糊搜索 |
| `page` | number | 否 | 页码，默认 1 |
| `page_size` | number | 否 | 每页数量，默认 50 |

示例：

```http
GET /api/documents?doc_type=pdf&page=1&page_size=20
```

成功响应：

```json
{
  "success": true,
  "data": {
    "total": 6,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "source": "ZRDDS用户手册.pdf",
        "doc_type": "pdf",
        "version": "unknown",
        "chunk_count": 120,
        "page_count": 56,
        "create_time": "2026-09-06 15:30:00",
        "operator": "小虎"
      }
    ]
  },
  "message": "ok",
  "request_id": "req_xxx"
}
```

### 5.2 获取知识库统计

```http
GET /api/documents/stats
```

成功响应：

```json
{
  "success": true,
  "data": {
    "source_count": 699,
    "chunk_count": 4300,
    "by_doc_type": {
      "pdf": 6,
      "c": 212,
      "cpp": 237,
      "java": 211,
      "manual": 33
    },
    "by_version": {
      "unknown": 650,
      "2.5.0": 49
    }
  },
  "message": "ok",
  "request_id": "req_xxx"
}
```

### 5.3 清空聊天历史

```http
DELETE /api/sessions/{session_id}/history
```

成功响应：

```json
{
  "success": true,
  "data": {
    "session_id": "user_001",
    "cleared": true
  },
  "message": "聊天历史已清空",
  "request_id": "req_xxx"
}
```

说明：

- 只清空 `chat_history` 中指定 session 的历史。
- 不删除知识库。

## 6. 文件入库接口

### 6.1 单文件上传

```http
POST /api/upload
```

请求类型：

```http
multipart/form-data
```

字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---:|---:|---|
| `file` | file | 是 | 上传文件 |
| `operator` | string | 否 | 操作人，默认 `小虎` |
| `overwrite` | boolean | 否 | 是否允许覆盖，第一版可不支持 |

支持文件：

```text
pdf / txt / csv / docx / html / htm
```

成功响应：

```json
{
  "success": true,
  "data": {
    "source": "ZRDDS用户手册.pdf",
    "status": "success",
    "chunk_count": 120,
    "message": "[成功]内容已成功载入向量库，共生成 120 个文本块，按每批 4 个文本块写入"
  },
  "message": "上传成功",
  "request_id": "req_xxx"
}
```

重复文件响应：

```json
{
  "success": true,
  "data": {
    "source": "ZRDDS用户手册.pdf",
    "status": "skipped",
    "chunk_count": 0,
    "message": "[跳过]内容已经存在知识库中"
  },
  "message": "文件已存在，跳过入库",
  "request_id": "req_xxx"
}
```

### 6.2 批量导入服务器本地目录

```http
POST /api/batch-ingest
```

请求：

```json
{
  "path": "D:\\project\\DDS\\ZRDDS\\ZRDDS-2.5.0\\doc\\html",
  "include_noise_html": false,
  "dry_run": false,
  "operator": "小虎"
}
```

字段说明：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---:|---:|---|---|
| `path` | string | 是 | 无 | 后端服务器本地文件或目录路径 |
| `include_noise_html` | boolean | 否 | `false` | 是否导入索引/搜索/源码等噪声 HTML |
| `dry_run` | boolean | 否 | `false` | 是否只扫描不入库 |
| `operator` | string | 否 | `小虎` | 操作人 |

成功响应：

```json
{
  "success": true,
  "data": {
    "path": "D:\\project\\DDS\\ZRDDS\\ZRDDS-2.5.0\\doc\\html",
    "dry_run": false,
    "include_noise_html": false,
    "total_files": 1783,
    "kept_files": 693,
    "skipped_noise_html": 1090,
    "success_count": 690,
    "skipped_count": 2,
    "failed_count": 1,
    "results": [
      {
        "source": "java\\zrdds_interface.html",
        "status": "success",
        "message": "[成功]内容已成功载入向量库，共生成 6 个文本块，按每批 4 个文本块写入",
        "chunk_count": 6,
        "skipped_reason": null
      }
    ],
    "failures": [
      {
        "source": "java\\bad.html",
        "error": "decode failed"
      }
    ]
  },
  "message": "批量导入完成",
  "request_id": "req_xxx"
}
```

`dry_run=true` 时：

- 不调用 embedding。
- 不写 Chroma。
- 不写 `md5.text`。
- 只返回扫描统计和待导入/跳过列表。

### 6.3 批量导入进度接口

第一周如果时间紧，可以先不做异步任务，`/api/batch-ingest` 直接同步返回。

如果需要前端显示长任务进度，建议设计异步接口：

```http
POST /api/batch-ingest/jobs
GET /api/batch-ingest/jobs/{job_id}
```

创建任务响应：

```json
{
  "success": true,
  "data": {
    "job_id": "ingest_20260906_153000",
    "status": "running"
  },
  "message": "批量导入任务已启动",
  "request_id": "req_xxx"
}
```

查询任务响应：

```json
{
  "success": true,
  "data": {
    "job_id": "ingest_20260906_153000",
    "status": "running",
    "current": 30,
    "total": 693,
    "current_source": "cpp\\class_d_d_s_1_1_data_reader.html",
    "success_count": 28,
    "skipped_count": 1,
    "failed_count": 1
  },
  "message": "ok",
  "request_id": "req_xxx"
}
```

`status` 可选：

```text
pending / running / finished / failed / cancelled
```

## 7. 配置接口

### 7.1 获取运行配置

```http
GET /api/config
```

成功响应：

```json
{
  "success": true,
  "data": {
    "embedding_provider": "ollama",
    "embedding_model_name": "bge-m3",
    "ollama_base_url": "http://localhost:11434",
    "chat_model_name": "qwen3-max",
    "rerank_model_name": "qwen3-rerank",
    "default_retrieval_mode": "hybrid",
    "vector_top_k": 10,
    "bm25_top_k": 10,
    "rrf_top_k": 10,
    "rerank_top_k": 5,
    "embedding_batch_size": 4
  },
  "message": "ok",
  "request_id": "req_xxx"
}
```

### 7.2 临时切换检索模式

第一版建议不要做全局写配置接口，避免多人联调互相影响。

前端每次调用 `/api/chat` 或 `/api/retrieve` 时传：

```json
{
  "retrieval_mode": "hybrid"
}
```

后端只对本次请求生效。

## 8. 前端页面与接口对应

### 8.1 问答助手页面

使用接口：

- `GET /api/health`
- `POST /api/chat`
- 可选：`POST /api/chat/stream`
- `DELETE /api/sessions/{session_id}/history`

页面能力：

- 展示对话。
- 支持选择 `hybrid/vector`。
- 展示引用来源。
- 展示命中文档片段。
- 清空当前会话历史。

### 8.2 文档库页面

使用接口：

- `GET /api/documents`
- `GET /api/documents/stats`
- `POST /api/upload`
- `POST /api/batch-ingest`

页面能力：

- 查看已入库文档。
- 按 `doc_type` 过滤。
- 搜索 source。
- 单文件上传。
- 输入服务器本地目录批量导入。
- 查看导入成功/跳过/失败结果。

### 8.3 系统状态页面

使用接口：

- `GET /api/health`
- `GET /api/config`
- `GET /api/documents/stats`

页面能力：

- 展示 Ollama 状态。
- 展示 embedding 模型。
- 展示 LLM/rerank 模型。
- 展示知识库 chunk 数、文档数。
- 展示默认检索模式。

## 9. RAG 服务内部接口建议

FastAPI 层可以封装 v2 当前服务，不要求前端知道这些类。

### 9.1 检索服务

建议内部稳定入口：

```python
VectorStoreService.search(query: str, mode: str | None = None) -> list[Document]
```

返回 LangChain `Document`，由 API 层转换为 `RetrievedDocument`。

### 9.2 问答服务

当前可复用：

```python
RagService().chain.invoke({"input": question}, config.session_config)
RagService().chain.stream({"input": question}, config.session_config)
```

后续建议增加一个更适合 API 的方法：

```python
RagService.answer(
    question: str,
    session_id: str,
    retrieval_mode: str = "hybrid",
    return_context: bool = True,
) -> dict
```

这样 API 层不用解析 LangChain chain 的中间结构。

### 9.3 入库服务

当前可复用：

```python
KnowledgeBaseService.upload_documents(
    documents=documents,
    filename=source,
    file_md5=file_md5,
)
```

API 层负责：

- 保存上传文件到临时文件。
- 调用 `DocumentLoaderService.load()`。
- 调用 `KnowledgeBaseService.upload_documents()`。
- 删除临时文件。

## 10. rag-benchmark 对接建议

评测器建议优先对接 `/api/retrieve`，或写 Python adapter 直接调用 `VectorStoreService.search()`。

Retrieval-only 评测需要每个返回文档有稳定 ID：

```text
source_chunk_id
```

建议评测数据集中的 `gold_chunk_ids` 后续使用：

```text
ZRDDS用户手册.pdf#12
cpp\class_d_d_s_1_1_data_reader.html#0
```

而不是旧 Chroma UUID。这样重建向量库后，只要 source 和 chunk 规则稳定，评测集仍可复用。

## 11. 第一周实现优先级

### 必须完成

1. `GET /api/health`
2. `POST /api/chat`
3. `POST /api/retrieve`
4. `GET /api/documents`
5. `POST /api/upload`
6. `POST /api/batch-ingest`

### 可以延后

1. `POST /api/chat/stream`
2. 异步批量导入 job 接口
3. `GET /api/config`
4. LLM judge 生成质量评测

### 不建议第一周做

1. 多用户权限系统。
2. 在线删除知识库文档。
3. 在线修改 embedding 模型。
4. 在线清空 Chroma。

## 12. 前后端 Mock 约定

前端可以在后端未完成前使用固定 mock：

```json
{
  "success": true,
  "data": {
    "answer": "这是模拟回答 [1]。",
    "session_id": "mock_session",
    "retrieval_mode": "hybrid",
    "citations": [
      {
        "index": 1,
        "source": "ZRDDS用户手册.pdf",
        "doc_type": "pdf",
        "version": "unknown",
        "page": "12",
        "chunk_id": 3,
        "source_chunk_id": "ZRDDS用户手册.pdf#3",
        "citation": "ZRDDS用户手册.pdf | p.12",
        "score": 0.9,
        "snippet": "这是模拟引用片段..."
      }
    ],
    "usage": {},
    "latency_ms": 100
  },
  "message": "ok",
  "request_id": "mock_req"
}
```

前端不要依赖未定义字段。后端可以增加字段，但不应删除本文档中的字段。

## 13. 安全与部署约定

### 13.1 API Key

- 百炼 API Key 只放后端环境变量或 `.env`。
- 前端不保存、不展示、不上传 API Key。
- 每个人本地开发可以使用自己的 `DASHSCOPE_API_KEY`。

### 13.2 批量导入路径

`/api/batch-ingest` 接收的是后端机器上的本地路径，不是前端浏览器所在机器路径。

上线时建议限制可导入根目录，例如：

```text
D:\project\DDS\ZRDDS
```

避免用户传入任意系统路径。

### 13.3 单机部署建议

第一版上线建议：

```text
Nginx / 静态服务：Vue dist
FastAPI + Uvicorn：API 服务
Ollama：本地 embedding 服务
Chroma：本地 chroma_db 目录
百炼：chat/rerank 云服务
```

## 14. 联调检查清单

上线演示前至少检查：

- `GET /api/health` 返回 `status=ok`。
- Ollama 已启动。
- `ollama list` 能看到 `bge-m3`。
- `DASHSCOPE_API_KEY` 已配置。
- `GET /api/documents/stats` 能看到非零 chunk。
- `POST /api/retrieve` 能返回 documents。
- `POST /api/chat` 能返回 answer 和 citations。
- 前端能展示引用。
- 大文件上传不会触发 Ollama tokenize refused。
- 批量导入重复文件会显示 skipped，不会重复入库。
