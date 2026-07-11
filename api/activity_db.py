"""
activity_db.py — 권리점검·상담 등 비(非)시세추정 활동 이력 저장소

시세추정 이력(history 테이블)과 같은 data/history.db 파일의 activity 테이블 사용.
홈 '최근 활동' 통합 피드가 두 테이블을 합쳐 보여준다.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_API_DIR      = Path(__file__).parent
_PROJECT_ROOT = _API_DIR.parent
DB = _PROJECT_ROOT / "data" / "history.db"

_DB_LOCK = threading.Lock()


@contextmanager
def _conn():
    with _DB_LOCK:
        con = sqlite3.connect(str(DB), check_same_thread=False, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
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
            CREATE TABLE IF NOT EXISTS activity (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                type     TEXT    NOT NULL,
                title    TEXT    NOT NULL,
                summary  TEXT    DEFAULT '',
                meta     TEXT    DEFAULT '{}',
                created  TEXT    DEFAULT (datetime('now','localtime')),
                user_id  INTEGER DEFAULT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity (created DESC)")
        con.commit()


def save(type_: str, title: str, summary: str = "",
         meta: Optional[dict] = None, user_id=None) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO activity (type, title, summary, meta, user_id) VALUES (?,?,?,?,?)",
            (type_, title, summary,
             json.dumps(meta or {}, ensure_ascii=False), user_id),
        )
        con.commit()
        return cur.lastrowid


def load_recent(limit: int = 10, user_id=None) -> list[dict]:
    with _conn() as con:
        if user_id is not None:
            rows = con.execute(
                "SELECT id, type, title, summary, meta, created "
                "FROM activity WHERE user_id=? ORDER BY created DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, type, title, summary, meta, created "
                "FROM activity ORDER BY created DESC LIMIT ?",
                (limit,),
            ).fetchall()
    items = []
    for r in rows:
        try:
            meta = json.loads(r["meta"] or "{}")
        except Exception:
            meta = {}
        items.append({
            "id": r["id"], "type": r["type"], "title": r["title"],
            "summary": r["summary"], "meta": meta, "created": r["created"],
        })
    return items
