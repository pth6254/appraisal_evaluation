"""
auth_db.py — 사용자 인증 DB (SQLite)
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_API_DIR = Path(__file__).parent
_PROJECT_ROOT = _API_DIR.parent
DB = _PROJECT_ROOT / "data" / "auth.db"


@contextmanager
def _conn():
    con = sqlite3.connect(str(DB), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
    finally:
        con.close()


def init():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    NOT NULL UNIQUE,
                password_hash TEXT    DEFAULT NULL,
                name          TEXT    DEFAULT '',
                avatar_url    TEXT    DEFAULT '',
                provider      TEXT    DEFAULT 'local',
                provider_id   TEXT    DEFAULT NULL,
                created       TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)")
        con.commit()


def create_local_user(email: str, password_hash: str, name: str = "") -> dict:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO users (email, password_hash, name, provider) VALUES (?,?,?,'local')",
            (email, password_hash, name),
        )
        con.commit()
    return get_by_id(cur.lastrowid)


def get_or_create_oauth_user(
    email: str, name: str, avatar_url: str, provider: str, provider_id: str
) -> dict:
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            con.execute(
                "UPDATE users SET name=?, avatar_url=?, provider=?, provider_id=? WHERE id=?",
                (name, avatar_url, provider, provider_id, row["id"]),
            )
            con.commit()
            return dict(row) | {"name": name, "avatar_url": avatar_url}
        cur = con.execute(
            "INSERT INTO users (email, name, avatar_url, provider, provider_id) VALUES (?,?,?,?,?)",
            (email, name, avatar_url, provider, provider_id),
        )
        con.commit()
    return get_by_id(cur.lastrowid)


def get_by_email(email: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None


def get_by_id(user_id: int) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None
