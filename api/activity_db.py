"""
activity_db.py — 권리점검·상담 등 비(非)시세추정 활동 이력 저장소 (PostgreSQL, SQLAlchemy)

시세추정 이력(HistoryRecord)과 같은 PostgreSQL 인스턴스의 activity 테이블 사용.
홈 '최근 활동' 통합 피드가 두 테이블을 합쳐 보여준다.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import delete, func, select

from db.base import init_db, session_scope
from db.models import ActivityRecord


def init():
    init_db()


def save(type_: str, title: str, summary: str = "",
         meta: Optional[dict] = None, user_id=None) -> int:
    with session_scope() as session:
        record = ActivityRecord(
            type=type_, title=title, summary=summary,
            meta=meta or {}, user_id=user_id,
        )
        session.add(record)
        session.flush()
        return record.id


def count_today(type_: str, user_id) -> int:
    """오늘(서버 로컬 기준) 해당 유형 활동 수 — 일일 사용량 상한 검사용"""
    if user_id is None:
        return 0
    with session_scope() as session:
        today_str = date.today().isoformat()  # 'created' 컬럼이 'YYYY-MM-DD HH:MM:SS' 문자열이라 접두 매칭
        stmt = select(func.count()).select_from(ActivityRecord).where(
            ActivityRecord.type == type_,
            ActivityRecord.user_id == user_id,
            ActivityRecord.created.like(f"{today_str}%"),
        )
        return session.scalar(stmt)


def delete_all(user_id) -> None:
    """사용자 활동 전체 삭제 (회원 탈퇴 시)"""
    if user_id is None:
        return
    with session_scope() as session:
        session.execute(delete(ActivityRecord).where(ActivityRecord.user_id == user_id))


def load_recent(limit: int = 10, user_id=None) -> list[dict]:
    with session_scope() as session:
        stmt = select(ActivityRecord).order_by(ActivityRecord.created.desc()).limit(limit)
        if user_id is not None:
            stmt = stmt.where(ActivityRecord.user_id == user_id)
        rows = session.scalars(stmt)
        return [
            {
                "id": r.id, "type": r.type, "title": r.title,
                "summary": r.summary, "meta": r.meta or {}, "created": r.created,
            }
            for r in rows
        ]
