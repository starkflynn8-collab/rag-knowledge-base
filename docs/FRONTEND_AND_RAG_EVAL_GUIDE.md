# 前端优化与 RAG 评测指南

这份文档说明两件事：

1. 做前端优化时该看什么、改什么
2. 做 RAG 评测时该怎么跑、怎么比

## 1. 前端优化时，先看哪些文档

前端优化不是先写页面，而是先对齐接口。

优先级如下：

1. `[API_CONTRACT.md](../API_CONTRACT.md)`  
   这是唯一的前后端协作标准。新增页面、字段、交互前，先确认这里有没有对应接口和返回结构。
2. `[backend/main.py](../backend/main.py)`  
   看当前已经暴露了哪些路由，前端只能调用这些接口。
3. `[frontend/src/api.js](../frontend/src/api.js)`  
   看前端当前封装了哪些请求，尽量在这里统一加接口，不要在页面里散写 `fetch`。
4. `[frontend/src/App.vue](../frontend/src/App.vue)`  
   看现有页面状态、交互和布局，优化时尽量沿用这些状态结构。
5. `[README.md](../README.md)`  
   看当前项目运行方式、模型配置和知识库约定。

## 2. 前端优化时，哪些东西可以改

只改前端相关内容：

- 页面布局
- 组件拆分
- 交互状态
- 请求封装
- 流式输出展示
- 文档列表展示
- 上传与批量导入 UI
- 系统状态展示

不要直接碰这些：

- Chroma
- Ollama
- 百炼模型调用细节
- RAG 检索逻辑
- 知识库清洗逻辑

## 3. 前端优化的标准流程

### 3.1 先定接口

如果页面要新增字段，先问三个问题：

1. 这个字段后端是否已经返回？
2. 如果没有，是否要更新 `API_CONTRACT.md`？
3. 如果要更新，后端和前端是否同时改？

### 3.2 再改请求层

如果只是新增/调整接口参数，优先改：

- `frontend/src/api.js`

不要在 `App.vue` 里直接拼请求。

### 3.3 再改页面层

页面层只做：

- 组件渲染
- 状态管理
- 事件触发
- 结果展示

### 3.4 最后联调

至少检查这些点：

- `/api/health` 能通
- `/api/chat` 能返回答案
- `/api/chat/stream` 能正常流式输出
- `/api/retrieve` 能返回引用
- `/api/documents` 能列出文档
- `/api/upload` 能入库
- `/api/batch-ingest` 能批量导入

## 4. 前端优化时推荐的改动顺序

1. 先做 API 封装统一
2. 再做页面布局和状态整理
3. 再做交互增强
4. 最后做样式优化

不要反过来。否则页面先写漂亮了，接口一改就要大回炉。

## 5. RAG 评测时先看哪些文档

RAG 评测主要看：

- `[API_CONTRACT.md](../API_CONTRACT.md)` 里的 `/api/retrieve`
- `[vector_stores.py](../vector_stores.py)`
- `[rag.py](../rag.py)`
- `[knowledge_base.py](../knowledge_base.py)`
- `[config_data.py](../config_data.py)`

如果你们要拿独立评测器跑，还要看外部项目：

- `D:\project\DDS\rag-benchmark`

## 6. RAG 评测优先评什么

先做检索评测，不要一上来就做生成评测。

优先级：

1. retrieval-only
2. vector vs hybrid 对比
3. rerank 前后对比
4. chunk 策略对比
5. embedding 模型对比

先确认“检索有没有命中”，再看“答案写得好不好”。

## 7. RAG 评测的最小闭环

### 7.1 准备测试集

建议每条数据至少包含：

- `question`
- `expected_sources`
- `expected_chunk_ids` 或 `expected_source_chunk_id`
- `expected_keywords`

示例：

```json
{
  "question": "ZRDDS 的排故流程包括什么？",
  "expected_sources": ["ZRDDS故障排查指南.pdf"],
  "expected_keywords": ["物理连接", "网络", "发布", "订阅"]
}
```

### 7.2 跑检索

建议先调用后端：

```http
POST /api/retrieve
```

请求里切换：

- `retrieval_mode=vector`
- `retrieval_mode=hybrid`
- `rerank=true/false`

看返回的 `documents` 是否命中预期来源。

### 7.3 看指标

至少统计：

- top1 命中率
- top3 命中率
- top5 命中率
- rerank 前后提升
- 失败样本数

### 7.4 固定版本再对比

每次只改一个点：

- BM25 分词
- chunk 大小
- rerank 开关
- query rewrite
- parent-child 检索
- embedding 模型

不能一口气改很多，不然不知道是哪项带来的变化。

## 8. 用 rag-benchmark 怎么搞

推荐做法是给 v2 单独做一个 adapter，接 `/api/retrieve` 或直接调 `VectorStoreService.search()`。

推荐路线：

1. 先让 benchmark 调 `/api/retrieve`
2. 跑 retrieval-only
3. 输出命中结果和分数
4. 再考虑生成质量评测

如果你们改了 embedding 或 chunk 规则，要注意：

- 知识库可能要重建
- 评测集最好用 `source_chunk_id`
- 不要依赖旧 Chroma UUID

## 9. 评测和前端优化的边界

前端优化解决的是：

- 用户怎么用
- 信息怎么展示
- 交互是否顺手

RAG 评测解决的是：

- 有没有召回到正确资料
- rerank 是否有效
- 检索策略是否更稳

这两件事不要混在一起做。

## 10. 最后一句

如果要在团队里执行，建议固定成一句话：

> 前端改动先看 `API_CONTRACT.md`，RAG 改动先跑 retrieval-only 评测。

