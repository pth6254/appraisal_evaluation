"""
test_transaction_store.py — 실거래가 로컬 스토어 단위 테스트
"""

from __future__ import annotations

import time

import pytest

import transaction_store
from price_engine import _endpoint_name

SAMPLE = {
    "price": 150000, "area_sqm": 84.97, "area_pyeong": 25.7, "per_sqm": 1765,
    "floor": "15", "year_built": "2008", "dong": "반포동",
    "apt_name": "래미안퍼스티지", "deal_year": "2026", "deal_month": "6",
}

KEY = ("RTMSDataSvcAptTrade", "주거용", "11650", "202606")


@pytest.fixture
def store(tmp_path, monkeypatch):
    """테스트 전용 임시 DB로 스토어 격리."""
    monkeypatch.setattr(transaction_store, "DB_PATH", str(tmp_path / "tx_test.db"))
    monkeypatch.setattr(transaction_store, "_INITIALIZED", False)
    transaction_store.init_store()
    return transaction_store


def test_miss_returns_none(store):
    assert store.get_month(*KEY) is None


def test_roundtrip(store):
    store.put_month(*KEY, [SAMPLE])
    rows = store.get_month(*KEY)
    assert rows is not None and len(rows) == 1
    assert rows[0]["price"] == 150000
    assert rows[0]["apt_name"] == "래미안퍼스티지"
    assert rows[0]["area_sqm"] == pytest.approx(84.97)


def test_empty_month_is_valid(store):
    """거래 0건 월은 [] — None(미적재)과 구분되어야 한다."""
    store.put_month(*KEY, [])
    assert store.get_month(*KEY) == []


def test_replace_is_idempotent(store):
    store.put_month(*KEY, [SAMPLE, SAMPLE])
    store.put_month(*KEY, [SAMPLE])          # 재수집 → 교체
    rows = store.get_month(*KEY)
    assert len(rows) == 1


def test_key_isolation(store):
    """endpoint·category·지역·월이 다르면 서로 간섭하지 않는다."""
    store.put_month(*KEY, [SAMPLE])
    other = ("RTMSDataSvcOffiTrade", "주거용", "11650", "202606")
    assert store.get_month(*other) is None
    store.put_month(*other, [])
    assert store.get_month(*other) == []
    assert len(store.get_month(*KEY)) == 1


def test_stale_entry_returns_none(store):
    store.put_month(*KEY, [SAMPLE])
    # fetched_at을 TTL 최대치(30일) 이전으로 강제 → 만료 판정
    with store._conn() as con:
        con.execute(
            "UPDATE ingest_log SET fetched_at = ?",
            (time.time() - transaction_store.TTL_COMPLETE_MONTH - 1,),
        )
        con.commit()
    assert store.get_month(*KEY) is None


def test_ttl_policy():
    """완결 월은 30일, 최근 월은 12시간 TTL."""
    from datetime import datetime

    now = datetime.now()
    current_ym = now.strftime("%Y%m")
    old_ym     = f"{now.year - 1}{now.month:02d}"

    assert transaction_store._ttl_for(current_ym) == transaction_store.TTL_RECENT_MONTH
    assert transaction_store._ttl_for(old_ym)     == transaction_store.TTL_COMPLETE_MONTH


def test_endpoint_name():
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    assert _endpoint_name(url) == "RTMSDataSvcAptTrade"
