from __future__ import annotations

import json
import sys
import time
import uuid
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_core.documents import Document as LCDocument
from backend.schemas import BatchIngestRequest, ChatRequest, RetrieveRequest
from backend.services import AppServices
from config_data import default_retrieval_mode


app = FastAPI(title="DDSRag v2 API", version="1.0")
services = AppServices()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def success_payload(data, message="ok", rid=None):
    return {
        "success": True,
        "data": data,
        "message": message,
        "request_id": rid or request_id(),
    }


def error_payload(code: str, message: str, detail: str | None = None, rid: str | None = None):
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
        },
        "request_id": rid or request_id(),
    }


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    rid = request_id()
    request.state.request_id = rid
    start = time.time()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Process-Time"] = f"{(time.time() - start):.3f}"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", request_id())
    detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
    code = "BAD_REQUEST"
    message = "请求失败"
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", code)
        message = exc.detail.get("message", message)
        detail = exc.detail.get("detail", detail)
    return JSONResponse(status_code=exc.status_code, content=error_payload(code, message, detail, rid))


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(
        status_code=500,
        content=error_payload("INTERNAL_ERROR", "内部错误", str(exc), rid),
    )


@app.get("/api/health")
async def health(request: Request):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(content=success_payload(services.health(), rid=rid))


@app.get("/api/config")
async def config_api(request: Request):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(content=success_payload(services.config_payload(), rid=rid))


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    rid = getattr(request.state, "request_id", request_id())
    try:
        data = services.answer(
            question=payload.question,
            session_id=payload.session_id,
            retrieval_mode=payload.retrieval_mode or default_retrieval_mode,
            top_k=payload.top_k,
            return_context=payload.return_context,
        )
        return JSONResponse(content=success_payload(data, rid=rid))
    except Exception as e:
        raise HTTPException(status_code=502, detail={"code": "LLM_FAILED", "message": "百炼模型调用失败", "detail": str(e)})


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request):
    rid = getattr(request.state, "request_id", request_id())

    def generate():
        try:
            docs, answer = services.stream_answer(
                question=payload.question,
                session_id=payload.session_id,
                retrieval_mode=payload.retrieval_mode or default_retrieval_mode,
                top_k=payload.top_k,
                return_context=payload.return_context,
            )

            yield "event: retrieval\n"
            yield f"data: {json.dumps({'retrieval_mode': payload.retrieval_mode, 'documents': services._format_documents(docs, include_text=False)}, ensure_ascii=False)}\n\n"

            yield "event: token\n"
            yield f"data: {json.dumps({'text': answer}, ensure_ascii=False)}\n\n"

            yield "event: done\n"
            yield f"data: {json.dumps({'answer': answer, 'citations': services._format_documents(docs, include_text=payload.return_context), 'latency_ms': None}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield "event: error\n"
            yield f"data: {json.dumps({'code': 'LLM_FAILED', 'message': '模型调用失败', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/retrieve")
async def retrieve(payload: RetrieveRequest, request: Request):
    rid = getattr(request.state, "request_id", request_id())
    data = services.retrieve(
        query=payload.query,
        retrieval_mode=payload.retrieval_mode or default_retrieval_mode,
        k=payload.k,
        rerank=payload.rerank,
    )
    return JSONResponse(content=success_payload(data, rid=rid))


@app.post("/retrieve")
async def retrieve_benchmark(request: Request):
    """rag-benchmark http_json adapter 兼容接口：检索"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "BAD_JSON", "message": "请求体不是有效 JSON"})
    query = body.get("query", "")
    k = body.get("k", 10)
    mode = body.get("retrieval_mode") or default_retrieval_mode
    docs = services._retrieve_raw(query=query, retrieval_mode=mode, k=k, rerank=True)
    result = services._format_documents(docs, include_text=True)
    # 将 chunk_id 移入 metadata，供 benchmark 提取
    for doc in result:
        if "metadata" not in doc:
            doc["metadata"] = {}
        doc["metadata"]["chunk_id"] = doc.pop("chunk_id", "unknown")
        doc["metadata"]["source"] = doc.pop("source", "unknown")
    return JSONResponse(content={"documents": result})


@app.post("/generate")
async def generate_benchmark(request: Request):
    """rag-benchmark http_json adapter 兼容接口：生成"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "BAD_JSON", "message": "请求体不是有效 JSON"})
    query = body.get("query", "")
    context = body.get("context", [])
    if isinstance(context, list):
        context_str = services.build_context([
            LCDocument(
                page_content=item.get("text", "") if isinstance(item, dict) else str(item),
                metadata=item.get("metadata", {}) if isinstance(item, dict) else {}
            )
            for item in context
        ]) if context else "无相关资料"
    else:
        context_str = str(context)
    answer_text = services.answer_chain.invoke(
        {"input": query, "context": context_str},
        {"configurable": {"session_id": f"benchmark_{request_id()}"}},
    )
    return JSONResponse(content={"answer": answer_text})


@app.get("/api/documents")
async def documents(
    request: Request,
    doc_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    rid = getattr(request.state, "request_id", request_id())
    data = services.list_documents(doc_type=doc_type, keyword=keyword, page=page, page_size=page_size)
    return JSONResponse(content=success_payload(data, rid=rid))


@app.get("/api/documents/stats")
async def documents_stats(request: Request):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(content=success_payload(services.document_stats(), rid=rid))


@app.delete("/api/sessions/{session_id}/history")
async def clear_history(session_id: str, request: Request):
    rid = getattr(request.state, "request_id", request_id())
    services.clear_history(session_id)
    return JSONResponse(content=success_payload({"session_id": session_id}, message="历史已清空", rid=rid))


@app.post("/api/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    operator: str = Form(default="小虎"),
):
    rid = getattr(request.state, "request_id", request_id())
    suffix = Path(file.filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await file.read())
        temp_path = Path(temp_file.name)

    try:
        data = services.upload_file(temp_path, file.filename, operator=operator)
        return JSONResponse(content=success_payload(data, rid=rid))
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "FILE_PROCESS_FAILED", "message": "文件处理失败", "detail": str(e)})
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post("/api/batch-ingest")
async def batch_ingest(payload: BatchIngestRequest, request: Request):
    rid = getattr(request.state, "request_id", request_id())
    data = services.batch_ingest(
        path=payload.path,
        include_noise_html=payload.include_noise_html,
        dry_run=payload.dry_run,
        operator=payload.operator,
    )
    return JSONResponse(content=success_payload(data, message="批量导入完成", rid=rid))


@app.get("/")
async def root():
    return {"message": "DDSRag v2 API is running"}
