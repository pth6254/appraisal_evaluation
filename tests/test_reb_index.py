"""
test_reb_index.py — 부동산원(R-ONE) 지수 시점수정 단위 테스트

네트워크 호출 없이 _get_month_rows_cached를 목킹해 검증한다.
"""

from __future__ import annotations

import pytest

import reb_index
import price_engine


# ─────────────────────────────────────────
#  픽스처: 월별 지수 목데이터
# ─────────────────────────────────────────

MOCK_INDEX = {
    # ym → {CLS_FULLNM: 지수}
    "202601": {
        "전국": 100.0,
        "서울": 100.0,
        "서울>강남지역>서초구": 100.0,
        "인천>중구": 100.0,
        "울산>중구": 90.0,
    },
    "202605": {
        "전국": 100.9,
        "서울": 102.0,
        "서울>강남지역>서초구": 103.0,
        "인천>중구": 100.5,
        "울산>중구": 89.0,
    },
    # 202606·202607: 미공표 (빈 dict)
    "202606": {},
    "202607": {},
}


@pytest.fixture
def mocked(monkeypatch):
    monkeypatch.setattr(reb_index, "REB_API_KEY", "test-key")
    monkeypatch.setattr(
        reb_index, "_get_month_rows_cached",
        lambda statbl, ym: MOCK_INDEX.get(ym, {}),
    )
    monkeypatch.setattr(reb_index, "_sido_of", lambda region: {
        "서초구": "서울특별시", "중구": "인천광역시",
    }.get(region, ""))
    return reb_index


# ─────────────────────────────────────────
#  지역 매칭
# ─────────────────────────────────────────

def test_match_sigungu_exact(mocked):
    assert mocked.get_index("주거용", "서초구", "202605") == 103.0


def test_match_ambiguous_gu_uses_sido(mocked):
    """'중구'는 인천·울산에 모두 존재 — 시도로 판별."""
    assert mocked.get_index("주거용", "중구", "202605") == 100.5


def test_match_fallback_to_sido(mocked):
    """시군구 미존재 → 시도 레벨."""
    mocked_sido = mocked._match_region(MOCK_INDEX["202605"], "없는구", "서울특별시")
    assert mocked_sido == 102.0


def test_match_fallback_to_national(mocked):
    val = mocked._match_region(MOCK_INDEX["202605"], "없는구", "")
    assert val == 100.9


# ─────────────────────────────────────────
#  시점수정 계수
# ─────────────────────────────────────────

def test_adj_factor_basic(mocked):
    r = mocked.get_adj_factor("주거용", "서초구", "202601", "202605")
    assert r is not None
    factor, desc = r
    assert factor == pytest.approx(1.03)
    assert "202601→202605" in desc


def test_adj_factor_lag_fallback(mocked):
    """기준시점(202607) 미공표 → 202605까지 소급 보정."""
    r = mocked.get_adj_factor("주거용", "서초구", "202601", "202607")
    assert r is not None
    factor, desc = r
    assert factor == pytest.approx(1.03)
    assert mocked.reached_ym(desc) == "202605"


def test_adj_factor_same_month_none(mocked):
    assert mocked.get_adj_factor("주거용", "서초구", "202605", "202605") is None


def test_adj_factor_unsupported_category(mocked):
    assert mocked.get_adj_factor("상업용", "서초구", "202601", "202605") is None


def test_disabled_without_key(monkeypatch):
    monkeypatch.setattr(reb_index, "REB_API_KEY", "")
    assert reb_index.get_adj_factor("주거용", "서초구", "202601", "202605") is None
    assert reb_index.get_index("주거용", "서초구", "202605") is None


# ─────────────────────────────────────────
#  유틸
# ─────────────────────────────────────────

def test_shift_ym():
    assert reb_index._shift_ym("202601", -1) == "202512"
    assert reb_index._shift_ym("202512", 1) == "202601"
    assert reb_index._shift_ym("202607", -6) == "202601"


def test_reached_ym():
    assert reb_index.reached_ym("부동산원 지수 202601→202605") == "202605"
    assert reb_index.reached_ym("설명 없음") == ""


# ─────────────────────────────────────────
#  price_engine 통합
# ─────────────────────────────────────────

def test_apply_time_adjustment_uses_index(mocked, monkeypatch):
    """지수 사용 가능 샘플은 reb_index, 아니면 근사율 폴백."""
    samples = [
        {"price": 100000, "deal_year": "2026", "deal_month": "1"},   # 202601 → 지수 적용
        {"price": 100000, "deal_year": "2026", "deal_month": "6"},   # 202606 미공표 → 폴백
    ]
    adjusted, rate = price_engine._apply_time_adjustment(
        samples, "주거용", "20260701", "서초구",
    )

    idx_adjusted = [s for s in adjusted if s["time_adj_source"] == "reb_index"]
    approx       = [s for s in adjusted if s["time_adj_source"] == "approx"]
    assert len(idx_adjusted) == 1 and len(approx) == 1

    # 지수 구간(202601→202605, ×1.03) + 잔여 2개월 근사율 복리
    s = idx_adjusted[0]
    expected = round(1.03 * (1 + rate) ** 2, 6)
    assert s["time_adj_factor"] == pytest.approx(expected)
    assert s["price"] == round(100000 * expected)
    assert s["original_price"] == 100000


def test_apply_time_adjustment_all_fallback_without_key(monkeypatch):
    monkeypatch.setattr(reb_index, "REB_API_KEY", "")
    samples = [{"price": 100000, "deal_year": "2026", "deal_month": "3"}]
    adjusted, rate = price_engine._apply_time_adjustment(
        samples, "주거용", "20260701", "서초구",
    )
    assert adjusted[0]["time_adj_source"] == "approx"
    assert adjusted[0]["time_adj_factor"] == pytest.approx((1 + rate) ** 4)
