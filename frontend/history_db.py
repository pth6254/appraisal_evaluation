"""
history_db.py — 감정평가 이력 저장소
개선:
  - WAL 모드 + check_same_thread=False
  - category를 analysis_result.agent_name 에서 올바르게 추출
  - load_all() 에 페이지네이션 (limit/offset) 추가
  - load_recent() 헬퍼 추가
  - 검색 기능(search_by_query) 추가
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

DB = Path(__file__).parent / "history.db"


# ─────────────────────────────────────────
#  커넥션 헬퍼
# ─────────────────────────────────────────

@contextmanager
def _conn():
    con = sqlite3.connect(str(DB), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    try:
        yield con
    finally:
        con.close()


# ─────────────────────────────────────────
#  초기화
# ─────────────────────────────────────────

def init():
    """앱 시작 시 1회 호출 — 테이블 없으면 생성"""
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                query     TEXT    NOT NULL,
                category  TEXT    DEFAULT '',
                result    TEXT    NOT NULL,
                created   TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        # 인덱스 추가 — 대시보드 정렬/필터 속도 향상
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_created
            ON history (created DESC)
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_category
            ON history (category)
        """)
        con.commit()


# ─────────────────────────────────────────
#  저장
# ─────────────────────────────────────────

from pydantic import BaseModel

def save(query: str, result: dict) -> int:
    ar       = result.get("analysis_result") or {}
    category = ar.get("agent_name", "") or result.get("category", "")

    # Pydantic 객체 포함된 값 직렬화 가능하게 변환
    def serialize(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        if isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [serialize(i) for i in obj]
        return obj

    serializable_result = serialize(result)

    with _conn() as con:
        cur = con.execute(
            "INSERT INTO history (query, category, result) VALUES (?,?,?)",
            (query, category, json.dumps(serializable_result, ensure_ascii=False)),
        )
        con.commit()
        return cur.lastrowid


# ─────────────────────────────────────────
#  조회
# ─────────────────────────────────────────

def count_all() -> int:
    """전체 이력 건수"""
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM history").fetchone()[0]


def load_all(limit: int = 100, offset: int = 0) -> list[dict]:
    """
    전체 이력 (최신순).
    limit/offset 으로 페이지네이션.
    """
    with _conn() as con:
        rows = con.execute(
            "SELECT id, query, category, result, created "
            "FROM history ORDER BY created DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    return [_row_to_dict(r) for r in rows]


def load_recent(n: int = 10) -> list[dict]:
    """최근 n 건 조회"""
    return load_all(limit=n, offset=0)


def load_one(record_id: int) -> Optional[dict]:
    """단건 조회"""
    with _conn() as con:
        row = con.execute(
            "SELECT query, result FROM history WHERE id=?", (record_id,)
        ).fetchone()
    if not row:
        return None
    d = json.loads(row["result"])
    d["query"] = row["query"]
    return d


def search_by_query(keyword: str, limit: int = 50) -> list[dict]:
    """query 컬럼 키워드 검색"""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, query, category, result, created "
            "FROM history WHERE query LIKE ? ORDER BY created DESC LIMIT ?",
            (f"%{keyword}%", limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def load_by_category(category: str, limit: int = 50) -> list[dict]:
    """유형별 이력 조회"""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, query, category, result, created "
            "FROM history WHERE category=? ORDER BY created DESC LIMIT ?",
            (category, limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ─────────────────────────────────────────
#  삭제
# ─────────────────────────────────────────

def delete_one(record_id: int):
    """이력 단건 삭제"""
    with _conn() as con:
        con.execute("DELETE FROM history WHERE id=?", (record_id,))
        con.commit()


def delete_all():
    """전체 이력 삭제 (대시보드 초기화용)"""
    with _conn() as con:
        con.execute("DELETE FROM history")
        con.commit()


# ─────────────────────────────────────────
#  내부 헬퍼
# ─────────────────────────────────────────

def _row_to_dict(r: sqlite3.Row) -> dict:
    item = {
        "id":       r["id"],
        "query":    r["query"],
        "category": r["category"],
        "created":  r["created"],
    }
    item.update(json.loads(r["result"]))
    # analysis_result 내부 필드를 최상위로 올림 (UI 호환)
    ar = item.get("analysis_result") or {}
    for key in (
        "estimated_value", "value_min", "value_max",
        "price_per_pyeong", "regional_avg_per_pyeong",
        "valuation_verdict", "deviation_pct",
        "cap_rate", "investment_grade", "annual_income",
        "appraisal_opinion", "strengths", "risk_factors", "recommendation",
        "comparable_avg", "comparable_count", "roi_5yr",
    ):
        if key not in item and key in ar:
            item[key] = ar[key]
    return item