"""
deps.py — FastAPI 공통 의존성
"""
from __future__ import annotations

from typing import Optional

from fastapi import Cookie, HTTPException, status

from api import auth_db, auth_utils


def get_current_user(auth_token: Optional[str] = Cookie(default=None)) -> dict:
    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다")
    try:
        user_id = auth_utils.decode_jwt(auth_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰")
    user = auth_db.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없음")
    return user


def get_optional_user(auth_token: Optional[str] = Cookie(default=None)) -> Optional[dict]:
    if not auth_token:
        return None
    try:
        user_id = auth_utils.decode_jwt(auth_token)
        return auth_db.get_by_id(user_id)
    except Exception:
        return None
