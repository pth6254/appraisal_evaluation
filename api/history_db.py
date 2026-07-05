"""
history_db.py — 감정평가 이력 저장소 (api/ 전용 복사본)

DB 위치: data/history.db (프로젝트 루트 기준)
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

_API_DIR      = Path(__file__).parent
_PROJECT_ROOT = _API_DIR.parent
DB = _PROJECT_ROOT / "data" / "history.db"

# WAL은 WSL /mnt/c (9p) 등 일부 파일시스템에서 "database is locked"를
# 유발할 수 있어 실패 시 기본 저널로 폴백하고, 접근을 락으로 직렬화한다.
_DB_LOCK = threading.Lock()


@contextmanager
def _conn():
    with _DB_LOCK:
        con = sqlite3.connect(str(DB), check_same_thread=False, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass  # WAL 미지원 파일시스템 → 기본(DELETE) 저널 유지
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=5000")
        try:
            yield con
        finally:
            con.close()


def init():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                query     TEXT    NOT NULL,
                category  TEXT    DEFAULT '',
                result    TEXT    NOT NULL,
                created   TEXT    DEFAULT (datetime('now','localtime')),
                user_id   INTEGER DEFAULT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_history_created ON history (created DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_history_category ON history (category)")
        con.commit()
        try:
            con.execute("ALTER TABLE history ADD COLUMN user_id INTEGER DEFAULT NULL")
            con.commit()
        except Exception:
            pass


def _serialize(obj):
    if isinstance(obj, BaseModel):
        return _serialize(obj.model_dump())
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def save(query: str, result: dict, user_id=None) -> int:
    ar       = result.get("analysis_result") or {}
    category = ar.get("agent_name", "") or result.get("category", "")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO history (query, category, result, user_id) VALUES (?,?,?,?)",
            (query, category, json.dumps(_serialize(result), ensure_ascii=False), user_id),
        )
        con.commit()
        return cur.lastrowid


def count_all(user_id=None) -> int:
    with _conn() as con:
        if user_id is not None:
            return con.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (user_id,)).fetchone()[0]
        return con.execute("SELECT COUNT(*) FROM history").fetchone()[0]


def load_all(limit: int = 100, offset: int = 0, user_id=None) -> list[dict]:
    with _conn() as con:
        if user_id is not None:
            rows = con.execute(
                "SELECT id, query, category, result, created "
                "FROM history WHERE user_id=? ORDER BY created DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, query, category, result, created "
                "FROM history ORDER BY created DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def load_one(record_id: int) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT query, result FROM history WHERE id=?", (record_id,)
        ).fetchone()
    if not row:
        return None
    d = json.loads(row["result"])
    d["query"] = row["query"]
    return d


def search_by_query(keyword: str, limit: int = 50, user_id=None) -> list[dict]:
    with _conn() as con:
        if user_id is not None:
            rows = con.execute(
                "SELECT id, query, category, result, created "
                "FROM history WHERE query LIKE ? AND user_id=? ORDER BY created DESC LIMIT ?",
                (f"%{keyword}%", user_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, query, category, result, created "
                "FROM history WHERE query LIKE ? ORDER BY created DESC LIMIT ?",
                (f"%{keyword}%", limit),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_one(record_id: int, user_id=None):
    with _conn() as con:
        if user_id is not None:
            con.execute("DELETE FROM history WHERE id=? AND user_id=?", (record_id, user_id))
        else:
            con.execute("DELETE FROM history WHERE id=?", (record_id,))
        con.commit()


def delete_all(user_id=None):
    with _conn() as con:
        if user_id is not None:
            con.execute("DELETE FROM history WHERE user_id=?", (user_id,))
        else:
            con.execute("DELETE FROM history")
        con.commit()


def _row_to_dict(r: sqlite3.Row) -> dict:
    item = {
        "id":       r["id"],
        "query":    r["query"],
        "category": r["category"],
        "created":  r["created"],
    }
    item.update(json.loads(r["result"]))
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
