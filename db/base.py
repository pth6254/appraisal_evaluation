"""
db/base.py — SQLAlchemy 엔진·세션

이전에는 auth/history/activity/cache/transactions/chat_corpus 가 각자
SQLite 파일(threading.Lock 으로 직렬화)을 열었다. uvicorn을 --workers N
으로 띄우면 워커마다 프로세스가 분리되어 각자 다른 파일을 보게 되므로
스케일아웃이 불가능했다 — 이 문제를 풀기 위해 단일 PostgreSQL 인스턴스로
모든 워커가 같은 데이터를 보게 한다.

DATABASE_URL 이 없으면 기동을 막는다. SQLite 폴백을 일부러 두지 않았다 —
"로컬은 SQLite, 운영은 Postgres"로 갈라지면 로컬에서 검증되지 않은 쿼리가
운영에서만 깨지는 사고가 반복되기 쉽다. 로컬 개발도 docker compose 로
Postgres·Redis를 띄우는 것을 기본 흐름으로 삼는다.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


# 엔진은 지연 생성한다 — 모듈 임포트 시점이 아니라 실제로 DB에 접근하는 첫 호출에서
# DATABASE_URL을 확인한다. 그래야 DB를 전혀 쓰지 않는 테스트(스코어링·시뮬레이션
# 계산 단위 테스트 등)가 Postgres 없이도 그대로 동작한다. auth_db 등 각 모듈은
# 함수 호출 시점에 session_scope()를 여는 기존 `_conn()` 패턴을 그대로 유지한다.
@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 설정되지 않았습니다. "
            "PostgreSQL 접속 문자열을 지정하세요 "
            "(예: postgresql://postgres:password@localhost:5432/real_estate_db). "
            "로컬 개발은 `docker compose up pgvector` 로 컨테이너를 먼저 띄우세요."
        )
    return create_engine(database_url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """세션 1개 = 트랜잭션 1개. with 블록이 정상 종료되면 commit, 예외면 rollback."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


_initialized = False


def init_db() -> None:
    """앱 테이블 생성 (idempotent — 기존 각 모듈의 init() 이 하던 CREATE TABLE IF NOT EXISTS 와 동등).

    스키마 변경 이력 관리는 아직 Alembic 등 마이그레이션 도구를 도입하지 않고
    create_all 에 의존한다 — 현재 규모(모델 9종)에서는 충분하지만, 컬럼 삭제·타입
    변경처럼 create_all 이 다루지 못하는 변경이 필요해지면 Alembic 도입을 검토할 것.
    """
    global _initialized
    if _initialized:
        return
    from db import models  # noqa: F401  (Base.metadata 에 모델을 등록하기 위한 임포트)
    Base.metadata.create_all(bind=get_engine())
    _initialized = True
