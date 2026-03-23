"""
cache_db.py — SQLite 캐싱 레이어
개선:
  - WAL 모드 + check_same_thread=False 로 멀티유저 동시성 처리
  - 커넥션 컨텍스트 매니저(_conn()) 로 항상 close 보장
  - init_cache_db() 중복 호출 안전 처리
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from collections import Counter
from contextlib import contextmanager
from typing import Any, Optional

DB_PATH      = os.getenv("SQLITE_CACHE_PATH", "./cache.db")
DEFAULT_TTL  = 60 * 60 * 24   # 24시간 (초)
_INITIALIZED = False           # 모듈 레벨 초기화 플래그


# ─────────────────────────────────────────
#  커넥션 헬퍼
# ─────────────────────────────────────────

@contextmanager
def _conn():
    """
    WAL 모드 + check_same_thread=False 커넥션.
    with 블록 종료 시 항상 close.
    """
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")   # 멀티 읽기 / 단일 쓰기 동시성
    con.execute("PRAGMA synchronous=NORMAL") # WAL 에선 NORMAL 이 안전하고 빠름
    try:
        yield con
    finally:
        con.close()


# ─────────────────────────────────────────
#  1. DB 초기화
# ─────────────────────────────────────────

INIT_SQL = """
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key   TEXT PRIMARY KEY,
    response    TEXT NOT NULL,
    created_at  REAL NOT NULL,
    ttl         REAL NOT NULL,
    hit_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS region_codes (
    region_name TEXT PRIMARY KEY,
    lawd_code   TEXT NOT NULL,
    sido        TEXT,
    sigungu     TEXT
);

CREATE TABLE IF NOT EXISTS embed_cache (
    text_hash    TEXT PRIMARY KEY,
    text_preview TEXT,
    vector_json  TEXT NOT NULL,
    created_at   REAL NOT NULL
);
"""


def init_cache_db():
    """캐시 DB 초기화 및 기본 지역코드 삽입 (중복 호출 안전)"""
    global _INITIALIZED
    if _INITIALIZED:
        return

    with _conn() as con:
        con.executescript(INIT_SQL)

        region_data = [
            # 서울
            ("강남구",    "11680", "서울특별시", "강남구"),
            ("서초구",    "11650", "서울특별시", "서초구"),
            ("송파구",    "11710", "서울특별시", "송파구"),
            ("강동구",    "11740", "서울특별시", "강동구"),
            ("마포구",    "11440", "서울특별시", "마포구"),
            ("용산구",    "11170", "서울특별시", "용산구"),
            ("성동구",    "11200", "서울특별시", "성동구"),
            ("광진구",    "11215", "서울특별시", "광진구"),
            ("영등포구",  "11560", "서울특별시", "영등포구"),
            ("강서구",    "11500", "서울특별시", "강서구"),
            ("노원구",    "11350", "서울특별시", "노원구"),
            ("은평구",    "11380", "서울특별시", "은평구"),
            ("서대문구",  "11410", "서울특별시", "서대문구"),
            ("종로구",    "11110", "서울특별시", "종로구"),
            ("중구",      "11140", "서울특별시", "중구"),
            ("동작구",    "11590", "서울특별시", "동작구"),
            ("관악구",    "11620", "서울특별시", "관악구"),
            ("강북구",    "11305", "서울특별시", "강북구"),
            ("도봉구",    "11320", "서울특별시", "도봉구"),
            ("중랑구",    "11260", "서울특별시", "중랑구"),
            ("동대문구",  "11230", "서울특별시", "동대문구"),
            ("성북구",    "11290", "서울특별시", "성북구"),
            ("양천구",    "11470", "서울특별시", "양천구"),
            ("구로구",    "11530", "서울특별시", "구로구"),
            ("금천구",    "11545", "서울특별시", "금천구"),
            # 경기
            ("수원시",    "41110", "경기도",     "수원시"),
            ("성남시",    "41130", "경기도",     "성남시"),
            ("고양시",    "41280", "경기도",     "고양시"),
            ("용인시",    "41460", "경기도",     "용인시"),
            ("부천시",    "41190", "경기도",     "부천시"),
            ("안양시",    "41170", "경기도",     "안양시"),
            ("화성시",    "41590", "경기도",     "화성시"),
            ("평택시",    "41220", "경기도",     "평택시"),
            ("시흥시",    "41390", "경기도",     "시흥시"),
            ("김포시",    "41570", "경기도",     "김포시"),
            ("하남시",    "41450", "경기도",     "하남시"),
            ("양평군",    "41830", "경기도",     "양평군"),
            ("과천시",    "41290", "경기도",     "과천시"),
            ("안성시",    "41550", "경기도",     "안성시"),
            ("오산시",    "41370", "경기도",     "오산시"),
            ("의왕시",    "41430", "경기도",     "의왕시"),
            ("군포시",    "41410", "경기도",     "군포시"),
            ("광명시",    "41210", "경기도",     "광명시"),
            ("광주시",    "41610", "경기도",     "광주시"),
            ("남양주시",  "41360", "경기도",     "남양주시"),
            ("구리시",    "41310", "경기도",     "구리시"),
            ("의정부시",  "41150", "경기도",     "의정부시"),
            ("파주시",    "41480", "경기도",     "파주시"),
            # 인천
            ("남동구",    "28200", "인천광역시", "남동구"),
            ("연수구",    "28185", "인천광역시", "연수구"),
            ("서구",      "28260", "인천광역시", "서구"),
            ("부평구",    "28237", "인천광역시", "부평구"),
            ("미추홀구",  "28177", "인천광역시", "미추홀구"),
            ("계양구",    "28245", "인천광역시", "계양구"),
            # 부산
            ("해운대구",  "26350", "부산광역시", "해운대구"),
            ("부산진구",  "26230", "부산광역시", "부산진구"),
            ("동래구",    "26260", "부산광역시", "동래구"),
            ("남구",      "26290", "부산광역시", "남구"),
            ("사상구",    "26530", "부산광역시", "사상구"),
            ("강서구",    "26440", "부산광역시", "강서구"),
            # 대구·대전·광주·울산
            ("수성구",    "27290", "대구광역시", "수성구"),
            ("달서구",    "27290", "대구광역시", "달서구"),
            ("유성구",    "30230", "대전광역시", "유성구"),
            ("서구",      "29140", "광주광역시", "서구"),
            ("울주군",    "31710", "울산광역시", "울주군"),
        ]

        con.executemany(
            """INSERT OR IGNORE INTO region_codes
               (region_name, lawd_code, sido, sigungu)
               VALUES (?, ?, ?, ?)""",
            region_data,
        )
        con.commit()

    _INITIALIZED = True
    print(f"[cache_db] 초기화 완료: {DB_PATH}")


# ─────────────────────────────────────────
#  2. API 응답 캐시
# ─────────────────────────────────────────

def _make_cache_key(namespace: str, **params) -> str:
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    h = hashlib.md5(payload.encode()).hexdigest()[:12]
    return f"{namespace}:{h}"


def cache_get(namespace: str, **params) -> Optional[Any]:
    """캐시 조회. 만료 시 자동 삭제 후 None 반환."""
    key = _make_cache_key(namespace, **params)
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT response, created_at, ttl FROM api_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()

            if not row:
                return None

            if time.time() - row["created_at"] > row["ttl"]:
                con.execute("DELETE FROM api_cache WHERE cache_key = ?", (key,))
                con.commit()
                return None

            con.execute(
                "UPDATE api_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (key,),
            )
            con.commit()
            print(f"[cache] HIT: {key}")
            return json.loads(row["response"])

    except Exception as e:
        print(f"[cache] 조회 오류: {e}")
        return None


def cache_set(value: Any, ttl: float = DEFAULT_TTL, namespace: str = "", **params):
    """캐시 저장."""
    key = _make_cache_key(namespace, **params)
    try:
        with _conn() as con:
            con.execute(
                """INSERT OR REPLACE INTO api_cache
                   (cache_key, response, created_at, ttl)
                   VALUES (?, ?, ?, ?)""",
                (key, json.dumps(value, ensure_ascii=False), time.time(), ttl),
            )
            con.commit()
    except Exception as e:
        print(f"[cache] 저장 오류: {e}")


def cached_api_call(func, namespace: str, ttl: float = DEFAULT_TTL, **params) -> Any:
    """API 함수를 캐시로 감싸는 범용 래퍼."""
    cached = cache_get(namespace, **params)
    if cached is not None:
        return cached
    print(f"[cache] MISS: {namespace} {params}")
    result = func(**params)
    if result:
        cache_set(result, ttl=ttl, namespace=namespace, **params)
    return result


# ─────────────────────────────────────────
#  3. 지역코드 룩업
# ─────────────────────────────────────────

def get_lawd_code(region_name: str) -> str:
    """행정구역명 → 국토부 법정동코드 5자리. 부분 매칭 지원."""
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT lawd_code FROM region_codes WHERE region_name = ?",
                (region_name,),
            ).fetchone()
            if row:
                return row["lawd_code"]

            row = con.execute(
                "SELECT lawd_code FROM region_codes WHERE region_name LIKE ?",
                (f"%{region_name}%",),
            ).fetchone()
            return row["lawd_code"] if row else ""
    except Exception as e:
        print(f"[cache_db] 지역코드 조회 오류: {e}")
        return ""


def add_region_code(region_name: str, lawd_code: str, sido: str = "", sigungu: str = ""):
    """지역코드 수동 추가."""
    try:
        with _conn() as con:
            con.execute(
                """INSERT OR REPLACE INTO region_codes
                   (region_name, lawd_code, sido, sigungu)
                   VALUES (?, ?, ?, ?)""",
                (region_name, lawd_code, sido, sigungu),
            )
            con.commit()
    except Exception as e:
        print(f"[cache_db] 지역코드 추가 오류: {e}")


# ─────────────────────────────────────────
#  4. 임베딩 캐시
# ─────────────────────────────────────────

def embed_cache_get(text: str) -> Optional[list[float]]:
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    try:
        with _conn() as con:
            row = con.execute(
                "SELECT vector_json FROM embed_cache WHERE text_hash = ?",
                (text_hash,),
            ).fetchone()
            return json.loads(row["vector_json"]) if row else None
    except Exception as e:
        print(f"[cache_db] 임베딩 조회 오류: {e}")
        return None


def embed_cache_set(text: str, vector: list[float]):
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    try:
        with _conn() as con:
            con.execute(
                """INSERT OR REPLACE INTO embed_cache
                   (text_hash, text_preview, vector_json, created_at)
                   VALUES (?, ?, ?, ?)""",
                (text_hash, text[:100], json.dumps(vector), time.time()),
            )
            con.commit()
    except Exception as e:
        print(f"[cache_db] 임베딩 저장 오류: {e}")


# ─────────────────────────────────────────
#  5. 캐시 통계
# ─────────────────────────────────────────

def cache_stats() -> dict:
    try:
        with _conn() as con:
            api_count    = con.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0]
            total_hits   = con.execute("SELECT COALESCE(SUM(hit_count),0) FROM api_cache").fetchone()[0]
            region_count = con.execute("SELECT COUNT(*) FROM region_codes").fetchone()[0]
            embed_count  = con.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0]
        return {
            "api_cache_entries": api_count,
            "total_cache_hits":  total_hits,
            "region_codes":      region_count,
            "embed_cache":       embed_count,
            "db_path":           DB_PATH,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    init_cache_db()
    stats = cache_stats()
    print("\n캐시 DB 현황:")
    for k, v in stats.items():
        print(f"  {k}: {v}")