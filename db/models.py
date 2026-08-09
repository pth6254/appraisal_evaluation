"""
db/models.py — SQLAlchemy ORM 모델

기존 6개 SQLite 모듈의 테이블을 그대로 옮겼다 (컬럼 이름·의미 동일).
JSON 컬럼(result/meta/response/vector_json/embedding)은 이전에는 텍스트로
저장해 각 모듈이 직접 json.dumps/loads 했지만, Postgres의 JSON 타입을 써서
그 왕복 변환을 SQLAlchemy에 맡긴다.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


def _now_str() -> str:
    """
    'created' 컬럼 기본값.

    이전 SQLite 스키마는 `datetime('now','localtime')` 로 서버 로컬시각 문자열을
    저장했고, 프론트(page.tsx/dashboard/page.tsx)는 그 문자열을 그대로
    slice(0,10)/slice(0,16) 해서 날짜만 잘라 쓴다. Postgres의 서버 시각(UTC 기준
    TIMESTAMP)으로 바꾸면 표시 시각이 그만큼 밀리므로, 동일한 포맷의 문자열을
    애플리케이션(파이썬) 레벨에서 그대로 생성해 하위 호환을 유지한다.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────
#  인증 (구 api/auth_db.py)
# ─────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    name: Mapped[str] = mapped_column(String(100), default="")
    avatar_url: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(20), default="local")
    provider_id: Mapped[str | None] = mapped_column(String(255), default=None)
    created: Mapped[str] = mapped_column(String(32), default=_now_str)

    # 비밀번호를 마지막으로 변경한 시각. JWT 는 stateless 라 서버가 발급된 토큰을
    # 직접 폐기할 수 없으므로, 발급 시각 대신 이 값을 토큰에 함께 넣고 검증 때
    # 대조한다 — 비밀번호가 바뀌면 값이 달라져 기존 세션이 전부 무효가 된다
    # (계정 탈취 후 비밀번호를 바꿔도 공격자 세션이 살아있는 문제를 막는다).
    #
    # NULL = 가입 이후 한 번도 변경한 적 없음. 이 경우 pwd_at 클레임이 없는
    # 기존 토큰도 그대로 통과시킨다 (컬럼 추가 이전 발급분 호환).
    password_changed_at: Mapped[str | None] = mapped_column(String(32), default=None)


# ─────────────────────────────────────────
#  시세추정 이력 (구 api/history_db.py)
# ─────────────────────────────────────────

class HistoryRecord(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="")
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created: Mapped[str] = mapped_column(String(32), default=_now_str, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), default=None, index=True
    )


# ─────────────────────────────────────────
#  권리점검·상담 활동 피드 (구 api/activity_db.py)
# ─────────────────────────────────────────

class ActivityRecord(Base):
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[str] = mapped_column(String(32), default=_now_str, index=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), default=None, index=True
    )


# ─────────────────────────────────────────
#  API 응답 캐시 · 지역코드 · 임베딩 캐시 (구 backend/cache_db.py)
# ─────────────────────────────────────────

class ApiCache(Base):
    __tablename__ = "api_cache"

    cache_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    ttl: Mapped[float] = mapped_column(Float, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)


class RegionCode(Base):
    __tablename__ = "region_codes"

    region_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    lawd_code: Mapped[str] = mapped_column(String(10), nullable=False)
    sido: Mapped[str] = mapped_column(String(30), default="")
    sigungu: Mapped[str] = mapped_column(String(30), default="")


class EmbedCache(Base):
    __tablename__ = "embed_cache"

    text_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    text_preview: Mapped[str] = mapped_column(Text, default="")
    vector_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)


# ─────────────────────────────────────────
#  실거래가 로컬 스토어 (구 backend/transaction_store.py)
# ─────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    lawd_cd: Mapped[str] = mapped_column(String(10), nullable=False)
    deal_ym: Mapped[str] = mapped_column(String(6), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    area_sqm: Mapped[float | None] = mapped_column(Float, default=None)
    area_pyeong: Mapped[float | None] = mapped_column(Float, default=None)
    per_sqm: Mapped[int | None] = mapped_column(BigInteger, default=None)
    floor: Mapped[str | None] = mapped_column(String(20), default=None)
    year_built: Mapped[str | None] = mapped_column(String(10), default=None)
    dong: Mapped[str | None] = mapped_column(String(50), default=None)
    apt_name: Mapped[str | None] = mapped_column(String(100), default=None)
    deal_year: Mapped[str | None] = mapped_column(String(10), default=None)
    deal_month: Mapped[str | None] = mapped_column(String(10), default=None)

    __table_args__ = (
        Index("idx_tx_key", "endpoint", "category", "lawd_cd", "deal_ym"),
        Index("idx_tx_apt", "lawd_cd", "apt_name"),
    )


class IngestLog(Base):
    __tablename__ = "ingest_log"

    endpoint: Mapped[str] = mapped_column(String(50), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    lawd_cd: Mapped[str] = mapped_column(String(10), primary_key=True)
    deal_ym: Mapped[str] = mapped_column(String(6), primary_key=True)
    fetched_at: Mapped[float] = mapped_column(Float, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)


# ─────────────────────────────────────────
#  법률·세금 상담 RAG 코퍼스 (구 backend/chat_corpus.py)
# ─────────────────────────────────────────

class ChatChunk(Base):
    __tablename__ = "chat_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON, default=None)
