from __future__ import annotations

import json
import mimetypes
import sys
import time
import uuid
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_core.documents import Document as LCDocument
from auth_store import authenticate, create_auth_session, register_user, revoke_auth_session, user_payload
from backend.auth import get_current_user, require_admin, require_upload, require_model_switch
from auth_store import list_users, set_user_permissions
from backend.schemas import UserPermissionsUpdate
from backend.schemas import BatchIngestRequest, ChatRequest, LoginRequest, ModelSwitchRequest, RegisterRequest, RetrieveRequest, SessionTitleUpdate
from backend.services import AppServices
from config_data import default_retrieval_mode
import config_data as config


app = FastAPI(title="DDSRag v2 API", version="1.0")
services = AppServices()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
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


@app.post("/api/auth/login")
async def login(payload: LoginRequest, response: Response, request: Request):
    user = authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_CREDENTIALS", "message": "用户名或密码错误"},
        )
    token = create_auth_session(user.id)
    result = JSONResponse(
        content=success_payload(
            user_payload(user),
            message="登录成功",
            rid=getattr(request.state, "request_id", request_id()),
        )
    )
    result.set_cookie(
        key=config.auth_cookie_name,
        value=token,
        max_age=config.auth_cookie_max_age,
        httponly=True,
        secure=config.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return result

@app.post("/api/auth/register")
async def register(payload: RegisterRequest, request: Request):
    try:
        user = register_user(payload.username, payload.password, payload.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "USERNAME_EXISTS", "message": str(exc)})
    token = create_auth_session(user.id)
    result = JSONResponse(content=success_payload(user_payload(user), message="注册成功"))
    result.set_cookie(key=config.auth_cookie_name, value=token, max_age=config.auth_cookie_max_age, httponly=True, secure=config.auth_cookie_secure, samesite="lax", path="/")
    return result


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    revoke_auth_session(request.cookies.get(config.auth_cookie_name))
    result = JSONResponse(
        content=success_payload(
            {},
            message="已退出登录",
            rid=getattr(request.state, "request_id", request_id()),
        )
    )
    result.delete_cookie(config.auth_cookie_name, path="/")
    return result


@app.get("/api/auth/me")
async def me(request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(content=success_payload(user_payload(user), rid=rid))


@app.get("/api/config")
async def config_api(request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(content=success_payload(services.config_payload(), rid=rid))


@app.get('/api/admin/users')
def admin_users(user=Depends(require_admin)):
    return success_payload(list_users())


@app.post('/api/admin/users', status_code=201)
def admin_create_user(payload: RegisterRequest, user=Depends(require_admin)):
    try:
        created = register_user(payload.username, payload.password, payload.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={'code': 'USERNAME_EXISTS', 'message': str(exc)})
    return success_payload(user_payload(created), message='用户已创建')


@app.patch('/api/admin/users/{user_id}/permissions')
def update_user_permissions(user_id: int, payload: UserPermissionsUpdate, user=Depends(require_admin)):
    try:
        set_user_permissions(user_id, payload.can_upload, payload.can_switch_models, payload.enabled)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return success_payload({}, message='权限已保存')


@app.post("/api/models/switch")
async def switch_models(payload: ModelSwitchRequest, request: Request, user=Depends(require_model_switch)):
    rid = getattr(request.state, "request_id", request_id())
    try:
        data = services.switch_model_mode(payload.mode)
        return JSONResponse(content=success_payload(data, message="模型模式已切换", rid=rid))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_MODEL_MODE", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"code": "MODEL_SWITCH_FAILED", "message": "模型模式切换失败", "detail": str(exc)})


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    session_id = payload.session_id or f"session_{uuid.uuid4().hex}"
    try:
        services.ensure_session(user, session_id)
        data = services.answer(
            question=payload.question,
            session_id=session_id,
            retrieval_mode=payload.retrieval_mode or default_retrieval_mode,
            top_k=payload.top_k,
            return_context=payload.return_context,
        )
        return JSONResponse(content=success_payload(data, rid=rid))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"code": "SESSION_FORBIDDEN", "message": str(exc)})
    except Exception as e:
        raise HTTPException(status_code=502, detail={"code": "LLM_FAILED", "message": "生成模型调用失败", "detail": str(e)})


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    session_id = payload.session_id or f"session_{uuid.uuid4().hex}"
    try:
        services.ensure_session(user, session_id)
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "SESSION_FORBIDDEN", "message": str(exc)},
        )

    def generate():
        try:
            docs, scores, answer = services.stream_answer(
                question=payload.question,
                session_id=session_id,
                retrieval_mode=payload.retrieval_mode or default_retrieval_mode,
                top_k=payload.top_k,
                return_context=payload.return_context,
            )

            top_score = scores[0] if scores else 0.0
            refused = (
                not services.is_small_talk(payload.question)
                and top_score < config.refusal_score_threshold
            )

            yield "event: retrieval\n"
            yield f"data: {json.dumps({'retrieval_mode': payload.retrieval_mode, 'documents': services._format_documents(docs, include_text=False, scores=scores)}, ensure_ascii=False)}\n\n"

            yield "event: token\n"
            yield f"data: {json.dumps({'text': answer}, ensure_ascii=False)}\n\n"

            yield "event: done\n"
            yield f"data: {json.dumps({'answer': answer, 'refused': refused, 'refusal_score': top_score if refused else None, 'citations': services._format_documents(docs, include_text=payload.return_context, scores=scores), 'latency_ms': None}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield "event: error\n"
            yield f"data: {json.dumps({'code': 'LLM_FAILED', 'message': '生成模型调用失败', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/retrieve")
async def retrieve(payload: RetrieveRequest, request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    data = services.retrieve(
        query=payload.query,
        retrieval_mode=payload.retrieval_mode or default_retrieval_mode,
        k=payload.k,
        rerank=payload.rerank,
    )
    return JSONResponse(content=success_payload(data, rid=rid))


@app.post("/retrieve")
async def retrieve_benchmark(request: Request, user=Depends(get_current_user)):
    """rag-benchmark http_json adapter 兼容接口：检索"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "BAD_JSON", "message": "请求体不是有效 JSON"})
    query = body.get("query", "")
    k = body.get("k", 10)
    mode = body.get("retrieval_mode") or default_retrieval_mode
    docs, scores = services._retrieve_raw(query=query, retrieval_mode=mode, k=k, rerank=True)
    result = services._format_documents(docs, include_text=True, scores=scores)
    # 将 chunk_id 移入 metadata，供 benchmark 提取
    for doc in result:
        if "metadata" not in doc:
            doc["metadata"] = {}
        doc["metadata"]["chunk_id"] = doc.pop("chunk_id", "unknown")
        doc["metadata"]["source"] = doc.pop("source", "unknown")
    return JSONResponse(content={"documents": result})


@app.post("/generate")
async def generate_benchmark(request: Request, user=Depends(get_current_user)):
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
    benchmark_session_id = f"benchmark_{request_id()}"
    services.ensure_session(user, benchmark_session_id)
    answer_text = services.answer_chain.invoke(
        {"input": query, "context": context_str},
        {"configurable": {"session_id": benchmark_session_id}},
    )
    return JSONResponse(content={"answer": answer_text})


@app.get("/api/documents")
async def documents(
    request: Request,
    user=Depends(get_current_user),
    doc_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    rid = getattr(request.state, "request_id", request_id())
    data = services.list_documents(doc_type=doc_type, keyword=keyword, page=page, page_size=page_size)
    return JSONResponse(content=success_payload(data, rid=rid))


@app.get("/api/documents/stats")
async def documents_stats(request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(content=success_payload(services.document_stats(), rid=rid))


@app.get("/api/documents/preview")
async def document_preview(
    request: Request,
    user=Depends(get_current_user),
    source_path: str = Query(..., min_length=1),
    limit: int = Query(default=80, ge=1, le=200),
):
    rid = getattr(request.state, "request_id", request_id())
    try:
        data = services.document_preview(source_path, limit=limit)
        return JSONResponse(content=success_payload(data, rid=rid))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "知识库中没有找到该文档", "detail": str(exc)},
        )


@app.get("/api/documents/html")
async def html_document(
    request: Request,
    user=Depends(get_current_user),
    source_path: str = Query(..., min_length=1),
):
    try:
        html_path = services.html_source_file(source_path)
        return FileResponse(
            path=html_path,
            media_type="text/html",
            headers={"Content-Disposition": "inline"},
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "HTML_NOT_FOUND", "message": "原始 HTML 页面不存在", "detail": str(exc)},
        )


@app.get("/api/html/{file_path:path}")
async def html_file(file_path: str, user=Depends(get_current_user)):
    try:
        asset_path = services.html_source_asset(file_path)
        media_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
        return FileResponse(
            path=asset_path,
            media_type=media_type,
            headers={"Content-Disposition": "inline"},
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "HTML_NOT_FOUND", "message": "原始 HTML 页面不存在", "detail": str(exc)},
        )


@app.get("/api/sessions")
async def sessions(request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    return JSONResponse(content=success_payload(services.list_sessions(user), rid=rid))


@app.get("/api/sessions/{session_id}/history")
async def session_history(session_id: str, request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    try:
        data = services.get_session_history(user, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": str(exc)})
    return JSONResponse(content=success_payload(data, rid=rid))


@app.patch("/api/sessions/{session_id}/title")
async def update_session_title(session_id: str, payload: SessionTitleUpdate, request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    try:
        data = services.update_session_title(user, session_id, payload.title)
        return JSONResponse(content=success_payload(data, message="会话标题已更新", rid=rid))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SESSION_TITLE", "message": str(exc)})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": str(exc)})


@app.delete("/api/sessions/{session_id}/history")
async def clear_history(session_id: str, request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    try:
        services.clear_history(user, session_id)
        return JSONResponse(content=success_payload({"session_id": session_id}, message="历史已清空", rid=rid))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": str(exc)})


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, request: Request, user=Depends(get_current_user)):
    rid = getattr(request.state, "request_id", request_id())
    try:
        services.delete_session(user, session_id)
        return JSONResponse(content=success_payload({"session_id": session_id}, message="会话已删除", rid=rid))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SESSION_ID", "message": str(exc)})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": str(exc)})


@app.post("/api/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    operator: str = Form(default="小虎"),
    user=Depends(require_upload),
):
    rid = getattr(request.state, "request_id", request_id())
    suffix = Path(file.filename).suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await file.read())
        temp_path = Path(temp_file.name)

    try:
        data = services.upload_file(temp_path, file.filename, operator=user.display_name)
        return JSONResponse(content=success_payload(data, rid=rid))
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "FILE_PROCESS_FAILED", "message": "文件处理失败", "detail": str(e)})
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post("/api/batch-ingest")
async def batch_ingest(payload: BatchIngestRequest, request: Request, user=Depends(require_upload)):
    rid = getattr(request.state, "request_id", request_id())
    data = services.batch_ingest(
        path=payload.path,
        include_noise_html=payload.include_noise_html,
        dry_run=payload.dry_run,
        operator=user.display_name,
    )
    return JSONResponse(content=success_payload(data, message="批量导入完成", rid=rid))


@app.get("/")
async def root():
    return {"message": "DDSRag v2 API is running"}
