"""
test_rec_ui_smoke.py — 4_매물추천.py 페이지의 smoke 테스트

Streamlit 렌더링 없이:
  1. 페이지 파일이 컴파일 가능한지 (SyntaxError 없음)
  2. 유틸 함수 동작 확인
  3. 페이지가 의존하는 백엔드 import 경로 동작 확인
"""

from __future__ import annotations

import ast
import os
import sys

import pytest

# ─────────────────────────────────────────
#  경로 설정
# ─────────────────────────────────────────

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PAGE_PATH = os.path.join(_REPO_ROOT, "frontend", "pages", "4_매물추천.py")


# ─────────────────────────────────────────
#  컴파일 검사
# ─────────────────────────────────────────

class TestPageCompiles:
    def test_file_exists(self):
        assert os.path.isfile(_PAGE_PATH), f"파일 없음: {_PAGE_PATH}"

    def test_no_syntax_error(self):
        with open(_PAGE_PATH, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"SyntaxError in 4_매물추천.py: {e}")

    def test_imports_backend_path_setup(self):
        """sys.path append 패턴이 파일에 있는지 확인"""
        with open(_PAGE_PATH, encoding="utf-8") as f:
            source = f.read()
        assert "sys.path.append" in source

    def test_uses_run_recommendation(self):
        with open(_PAGE_PATH, encoding="utf-8") as f:
            source = f.read()
        assert "run_recommendation" in source

    def test_uses_property_query(self):
        with open(_PAGE_PATH, encoding="utf-8") as f:
            source = f.read()
        assert "PropertyQuery" in source

    def test_sample_data_notice_present(self):
        with open(_PAGE_PATH, encoding="utf-8") as f:
            source = f.read()
        assert "샘플" in source


# ─────────────────────────────────────────
#  유틸 함수 단위 테스트
# ─────────────────────────────────────────

# 유틸 함수를 직접 정의해 테스트 (페이지 import 없이)
def _parse_price_to_won(text: str) -> int:
    """4_매물추천.py 의 _parse_price_to_won 복사본"""
    if not text or not text.strip():
        return 0
    text = text.strip().replace(",", "").replace(" ", "").replace("천", "000")
    try:
        if "억" in text:
            parts = text.replace("만원", "").replace("만", "").split("억")
            eok = float(parts[0]) * 1_0000_0000
            man = float(parts[1]) * 10_000 if parts[1] else 0
            return int(eok + man)
        if "만원" in text or "만" in text:
            return int(float(text.replace("만원", "").replace("만", "")) * 10_000)
        val = float(text)
        return int(val) if val >= 10_000_000 else int(val * 10_000)
    except (ValueError, IndexError):
        return 0


def _fmt_won(won: int | None) -> str:
    if not won:
        return "—"
    eok = won // 1_0000_0000
    man = (won % 1_0000_0000) // 10_000
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


class TestParsePriceToWon:
    def test_empty_returns_zero(self):
        assert _parse_price_to_won("") == 0
        assert _parse_price_to_won("   ") == 0

    def test_eok_only(self):
        assert _parse_price_to_won("5억") == 500_000_000

    def test_eok_man(self):
        assert _parse_price_to_won("5억3000만") == 530_000_000

    def test_eok_chun(self):
        assert _parse_price_to_won("5억5천") == 550_000_000

    def test_man_only(self):
        assert _parse_price_to_won("5000만") == 50_000_000

    def test_large_eok(self):
        assert _parse_price_to_won("10억") == 1_000_000_000

    def test_15eok(self):
        assert _parse_price_to_won("15억") == 1_500_000_000

    def test_invalid_returns_zero(self):
        assert _parse_price_to_won("abc") == 0

    def test_comma_ignored(self):
        assert _parse_price_to_won("1,000,000,000") == 1_000_000_000

    def test_float_eok(self):
        assert _parse_price_to_won("2.5억") == 250_000_000


class TestFmtWon:
    def test_none_returns_dash(self):
        assert _fmt_won(None) == "—"

    def test_zero_returns_dash(self):
        assert _fmt_won(0) == "—"

    def test_10eok(self):
        assert _fmt_won(1_000_000_000) == "10억원"

    def test_10eok_5000man(self):
        assert _fmt_won(1_050_000_000) == "10억 5,000만원"

    def test_man_only(self):
        assert _fmt_won(50_000_000) == "5,000만원"


# ─────────────────────────────────────────
#  백엔드 통합 smoke
# ─────────────────────────────────────────

class TestBackendSmoke:
    def test_property_query_importable(self):
        from schemas.property_query import PropertyQuery
        q = PropertyQuery(intent="recommendation", region="마포구")
        assert q.region == "마포구"

    def test_run_recommendation_importable(self):
        from router import run_recommendation
        assert callable(run_recommendation)

    def test_run_recommendation_basic(self):
        from schemas.property_query import PropertyQuery
        from router import run_recommendation
        from tools.listing_tool import _load_listings
        _load_listings.cache_clear()

        q = PropertyQuery(intent="recommendation", region="마포구")
        state = run_recommendation(q, limit=3, run_appraisal=False)

        assert isinstance(state.get("results"), list)
        assert isinstance(state.get("report"), str)
        assert len(state["results"]) > 0
        _load_listings.cache_clear()

    def test_run_recommendation_returns_sorted_results(self):
        from schemas.property_query import PropertyQuery
        from router import run_recommendation
        from tools.listing_tool import _load_listings
        _load_listings.cache_clear()

        q = PropertyQuery(intent="recommendation")
        state = run_recommendation(q, limit=5, run_appraisal=False)
        scores = [r.total_score for r in state.get("results", [])]
        assert scores == sorted(scores, reverse=True)
        _load_listings.cache_clear()

    def test_run_recommendation_empty_on_no_match(self):
        from schemas.property_query import PropertyQuery
        from router import run_recommendation

        q = PropertyQuery(intent="recommendation", budget_max=10_000)
        state = run_recommendation(q, limit=5, run_appraisal=False)
        assert state.get("results") == [] or len(state.get("results", [])) == 0

    def test_run_recommendation_budget_filter(self):
        from schemas.property_query import PropertyQuery
        from router import run_recommendation
        from tools.listing_tool import _load_listings
        _load_listings.cache_clear()

        budget = 800_000_000
        q = PropertyQuery(intent="recommendation", budget_max=budget)
        state = run_recommendation(q, limit=10, run_appraisal=False)
        for r in state.get("results", []):
            assert r.listing.asking_price <= budget
        _load_listings.cache_clear()
