from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request

from auth_store import User, get_user_by_token
import config_data as config


def get_current_user(
    request: Request,
    token: str | None = Cookie(default=None, alias=config.auth_cookie_name),
) -> User:
    user = get_user_by_token(token)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "请先登录"},
        )
    request.state.user = user
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"code": "ADMIN_REQUIRED", "message": "需要管理员权限"},
        )
    return user


def require_upload(user: User = Depends(get_current_user)) -> User:
    if user.role != 'admin' and not user.can_upload:
        raise HTTPException(status_code=403, detail={'code': 'UPLOAD_FORBIDDEN', 'message': '没有上传文档权限'})
    return user


def require_model_switch(user: User = Depends(get_current_user)) -> User:
    if user.role != 'admin' and not user.can_switch_models:
        raise HTTPException(status_code=403, detail={'code': 'MODEL_SWITCH_FORBIDDEN', 'message': '没有模型切换权限'})
    return user
