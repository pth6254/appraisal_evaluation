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
        payload = auth_utils.decode_jwt_payload(auth_token)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰")
    user = auth_db.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없음")
    # 비밀번호 변경 이전에 발급된 토큰은 거부한다 (계정 탈취 후 비밀번호를
    # 바꿔도 공격자 세션이 살아있는 문제 방지).
    if not auth_utils.is_session_valid(payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 변경되어 다시 로그인해야 합니다",
        )
    return user


def get_optional_user(auth_token: Optional[str] = Cookie(default=None)) -> Optional[dict]:
    if not auth_token:
        return None
    try:
        payload = auth_utils.decode_jwt_payload(auth_token)
        user = auth_db.get_by_id(int(payload["sub"]))
    except Exception:
        return None
    if user and not auth_utils.is_session_valid(payload, user):
        return None
    return user
