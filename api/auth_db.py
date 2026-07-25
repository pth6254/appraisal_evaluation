"""
auth_db.py — 사용자 인증 DB (PostgreSQL, SQLAlchemy)

이전에는 SQLite 파일(data/auth.db)을 직접 열었다. db/base.py 의 공용
세션으로 옮기되, 호출부(api/routes/auth.py, api/deps.py 등)가 기대하는
함수 시그니처와 반환 형태(dict)는 그대로 유지한다.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from db.base import init_db, session_scope
from db.models import User


def init():
    """앱 전체 테이블을 생성한다 (history_db.init()/activity_db.init() 과 동일한 진입점).

    이름은 하위 호환을 위해 유지 — 실제로는 db.base.init_db() 로 위임한다.
    """
    init_db()


def _to_dict(user: User) -> dict:
    return {
        "id":            user.id,
        "email":         user.email,
        "password_hash": user.password_hash,
        "name":          user.name,
        "avatar_url":    user.avatar_url,
        "provider":      user.provider,
        "provider_id":   user.provider_id,
        "created":       user.created,
    }


def create_local_user(email: str, password_hash: str, name: str = "") -> dict:
    with session_scope() as session:
        user = User(email=email, password_hash=password_hash, name=name, provider="local")
        session.add(user)
        session.flush()
        return _to_dict(user)


def get_or_create_oauth_user(
    email: str, name: str, avatar_url: str, provider: str, provider_id: str
) -> dict:
    with session_scope() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user:
            user.name = name
            user.avatar_url = avatar_url
            user.provider = provider
            user.provider_id = provider_id
            session.flush()
            return _to_dict(user)
        user = User(
            email=email, name=name, avatar_url=avatar_url,
            provider=provider, provider_id=provider_id,
        )
        session.add(user)
        session.flush()
        return _to_dict(user)


def get_by_email(email: str) -> Optional[dict]:
    with session_scope() as session:
        user = session.scalar(select(User).where(User.email == email))
        return _to_dict(user) if user else None


def get_by_id(user_id: int) -> Optional[dict]:
    with session_scope() as session:
        user = session.get(User, user_id)
        return _to_dict(user) if user else None


def delete_user(user_id: int) -> None:
    """회원 탈퇴 — 계정 행 삭제 (이력·활동 삭제는 호출 측에서 함께 수행)"""
    with session_scope() as session:
        user = session.get(User, user_id)
        if user:
            session.delete(user)
