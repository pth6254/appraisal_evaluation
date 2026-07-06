"""
transaction_store.py — 국토부 실거래가 로컬 스토어 (SQLite)

price_engine이 MOLIT API에서 받아온 월 단위 실거래 데이터를
(endpoint, category, lawd_cd, deal_ym) 키로 적재하고,
동일 키 재조회 시 API 호출 없이 로컬 DB에서 반환한다.

적재 경로 2가지:
  1) write-through — price_engine._fetch_one_month 가 API 호출 성공 시 자동 적재
  2) batch ingest  — backend/tools/ingest_transactions.py 로 사전 수집

신선도(TTL) 정책:
  - 완결 월 (기준 2개월 이전): 30일 — 정정·해제 거래 반영 주기
  - 최근 월 (당월·전월):      12시간 — 신고 기한(30일) 내 데이터 계속 유입
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime

_BACKEND_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

DB_PATH = os.getenv(
    "TRANSACTIONS_DB_PATH",
    os.path.join(_PROJECT_ROOT, "data", "transactions.db"),
)

TTL_COMPLETE_MONTH = 60 * 60 * 24 * 30   # 30일 — 완결 월
TTL_RECENT_MONTH   = 60 * 60 * 12        # 12시간 — 당월·전월

_INITIALIZED = False

# 저장하는 샘플 필드 (price_engine._parse_items 출력과 1:1)
SAMPLE_FIELDS = [
    "price", "area_sqm", "area_pyeong", "per_sqm",
    "floor", "year_built", "dong", "apt_name",
    "deal_year", "deal_month",
]


# ─────────────────────────────────────────
#  커넥션 헬퍼
#  - WAL은 WSL /mnt/c (9p) 등 일부 파일시스템에서 공유메모리 미지원으로
#    "database is locked"를 유발 → 실패 시 기본 저널 모드로 폴백
#  - ThreadPoolExecutor 동시 접근 대비, 모든 DB 접근을 락으로 직렬화
#    (네트워크 I/O가 지배적이라 성능 영향 없음)
# ─────────────────────────────────────────

_DB_LOCK = threading.Lock()


@contextmanager
def _conn():
    with _DB_LOCK:
        con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
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


INIT_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint    TEXT NOT NULL,      -- RTMSDataSvcAptTrade 등
    category    TEXT NOT NULL,      -- 주거용/상업용/업무용/산업용/토지
    lawd_cd     TEXT NOT NULL,      -- 법정동코드 5자리
    deal_ym     TEXT NOT NULL,      -- YYYYMM
    price       INTEGER NOT NULL,   -- 거래금액 (만원)
    area_sqm    REAL,
    area_pyeong REAL,
    per_sqm     INTEGER,
    floor       TEXT,
    year_built  TEXT,
    dong        TEXT,
    apt_name    TEXT,
    deal_year   TEXT,
    deal_month  TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_key ON transactions (endpoint, category, lawd_cd, deal_ym);
CREATE INDEX IF NOT EXISTS idx_tx_apt ON transactions (lawd_cd, apt_name);

CREATE TABLE IF NOT EXISTS ingest_log (
    endpoint    TEXT NOT NULL,
    category    TEXT NOT NULL,
    lawd_cd     TEXT NOT NULL,
    deal_ym     TEXT NOT NULL,
    fetched_at  REAL NOT NULL,      -- epoch seconds
    row_count   INTEGER NOT NULL,
    PRIMARY KEY (endpoint, category, lawd_cd, deal_ym)
);
"""


def init_store():
    """스토어 DB 초기화 (중복 호출 안전)."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as con:
        con.executescript(INIT_SQL)
        con.commit()
    _INITIALIZED = True


# ─────────────────────────────────────────
#  TTL 판정
# ─────────────────────────────────────────

def _ttl_for(deal_ym: str) -> int:
    """완결 월(기준 2개월 이전)이면 긴 TTL, 최근 월이면 짧은 TTL."""
    now = datetime.now()
    try:
        ym = datetime.strptime(deal_ym, "%Y%m")
    except ValueError:
        return TTL_RECENT_MONTH
    months_ago = (now.year - ym.year) * 12 + (now.month - ym.month)
    return TTL_COMPLETE_MONTH if months_ago >= 2 else TTL_RECENT_MONTH


def _is_fresh(fetched_at: float, deal_ym: str) -> bool:
    return (time.time() - fetched_at) <= _ttl_for(deal_ym)


# ─────────────────────────────────────────
#  조회 / 적재
# ─────────────────────────────────────────

def get_month(endpoint: str, category: str, lawd_cd: str, deal_ym: str,
              ignore_ttl: bool = False) -> list[dict] | None:
    """
    적재된 월 데이터 반환.
    미적재 또는 TTL 만료 시 None (→ 호출측이 API 폴백).
    적재됐지만 거래 0건인 월은 빈 리스트 [] 반환 (유효한 결과).
    ignore_ttl=True: 백테스트 등 과거 데이터 분석용 — 만료돼도 반환.
    """
    init_store()
    key = (endpoint, category, lawd_cd, deal_ym)
    try:
        with _conn() as con:
            log = con.execute(
                """SELECT fetched_at FROM ingest_log
                   WHERE endpoint=? AND category=? AND lawd_cd=? AND deal_ym=?""",
                key,
            ).fetchone()
            if not log or (not ignore_ttl and not _is_fresh(log["fetched_at"], deal_ym)):
                return None

            rows = con.execute(
                f"""SELECT {', '.join(SAMPLE_FIELDS)} FROM transactions
                    WHERE endpoint=? AND category=? AND lawd_cd=? AND deal_ym=?""",
                key,
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[tx_store] 조회 오류: {e}")
        return None


def put_month(endpoint: str, category: str, lawd_cd: str, deal_ym: str, samples: list[dict]):
    """
    월 데이터 교체 적재 (기존 행 삭제 후 삽입 — 재수집 멱등).
    API 호출이 '성공'했을 때만 호출할 것 — 실패한 조회를 적재하면
    빈 결과가 TTL 동안 고착된다.
    """
    init_store()
    key = (endpoint, category, lawd_cd, deal_ym)
    try:
        with _conn() as con:
            con.execute(
                """DELETE FROM transactions
                   WHERE endpoint=? AND category=? AND lawd_cd=? AND deal_ym=?""",
                key,
            )
            con.executemany(
                f"""INSERT INTO transactions
                    (endpoint, category, lawd_cd, deal_ym, {', '.join(SAMPLE_FIELDS)})
                    VALUES (?, ?, ?, ?, {', '.join('?' * len(SAMPLE_FIELDS))})""",
                [key + tuple(s.get(f) for f in SAMPLE_FIELDS) for s in samples],
            )
            con.execute(
                """INSERT OR REPLACE INTO ingest_log
                   (endpoint, category, lawd_cd, deal_ym, fetched_at, row_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                key + (time.time(), len(samples)),
            )
            con.commit()
    except Exception as e:
        print(f"[tx_store] 적재 오류: {e}")


# ─────────────────────────────────────────
#  통계
# ─────────────────────────────────────────

def store_stats() -> dict:
    init_store()
    try:
        with _conn() as con:
            tx_count  = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            log_count = con.execute("SELECT COUNT(*) FROM ingest_log").fetchone()[0]
            regions   = con.execute("SELECT COUNT(DISTINCT lawd_cd) FROM ingest_log").fetchone()[0]
            ym_range  = con.execute(
                "SELECT MIN(deal_ym), MAX(deal_ym) FROM ingest_log"
            ).fetchone()
        return {
            "transactions":   tx_count,
            "ingested_keys":  log_count,
            "regions":        regions,
            "month_range":    f"{ym_range[0]} ~ {ym_range[1]}" if ym_range[0] else "—",
            "db_path":        DB_PATH,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    init_store()
    print("실거래가 스토어 현황:")
    for k, v in store_stats().items():
        print(f"  {k}: {v}")
