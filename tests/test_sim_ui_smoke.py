"""
test_sim_ui_smoke.py — 5_투자시뮬레이션.py 페이지 smoke 테스트 (Phase 4-4)

Streamlit 렌더링 없이:
  1. 페이지 파일 컴파일 가능 여부 (SyntaxError 없음)
  2. 유틸 함수 동작 확인 (_parse_price_to_won, _won_to_str, _fmt_won)
  3. session_state 연동 로직 단위 확인
  4. 백엔드 연결 smoke (run_simulation 임포트·호출)
  5. 추천 페이지(4_매물추천.py) 시뮬레이션 버튼 삽입 여부 확인
"""

from __future__ import annotations

import ast
import os
import sys

import pytest

# ─────────────────────────────────────────
#  경로 설정
# ─────────────────────────────────────────

_REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SIM_PAGE   = os.path.join(_REPO_ROOT, "frontend", "pages", "5_투자시뮬레이션.py")
_REC_PAGE   = os.path.join(_REPO_ROOT, "frontend", "pages", "4_매물추천.py")


# ─────────────────────────────────────────
#  컴파일 검사
# ─────────────────────────────────────────

class TestSimPageCompiles:
    def test_file_exists(self):
        assert os.path.isfile(_SIM_PAGE), f"파일 없음: {_SIM_PAGE}"

    def test_no_syntax_error(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"SyntaxError in 5_투자시뮬레이션.py: {e}")

    def test_uses_run_simulation(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "run_simulation" in source

    def test_uses_simulation_input(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "SimulationInput" in source

    def test_disclaimer_present(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "간이 계산" in source

    def test_session_state_listing_key(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "sim_from_listing" in source

    def test_session_state_applied_key(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "sim_listing_applied" in source

    def test_uses_router_import(self):
        """서비스 직접 호출이 아닌 router.run_simulation 사용 확인"""
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "from router import run_simulation" in source

    def test_rental_mode_radio_outside_form(self):
        """rental_mode 라디오가 st.form 이전에 위치하는지 확인"""
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        radio_pos = source.find("sim_rental_mode")
        form_pos  = source.find('st.form("sim5_form")')
        assert radio_pos != -1, "sim_rental_mode 키 없음"
        assert form_pos  != -1, "sim5_form 없음"
        assert radio_pos < form_pos, "rental_mode 라디오가 form 안에 있음"

    def test_widget_defaults_dict_present(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "_WIDGET_DEFAULTS" in source


class TestRecPageSimButton:
    def test_rec_page_exists(self):
        assert os.path.isfile(_REC_PAGE)

    def test_rec_page_has_sim_button(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "sim_btn_" in source, "시뮬레이션 버튼 key 없음"

    def test_rec_page_saves_listing(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "sim_from_listing" in source

    def test_rec_page_switch_to_sim(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "5_투자시뮬레이션" in source

    def test_rec_page_no_syntax_error(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"SyntaxError in 4_매물추천.py: {e}")


# ─────────────────────────────────────────
#  유틸 함수 단위 테스트
# ─────────────────────────────────────────

# 페이지 import 없이 함수를 직접 정의해서 테스트

def _parse_price_to_won(text: str) -> int:
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


def _won_to_str(won: int) -> str:
    if won <= 0:
        return ""
    eok = won // 1_0000_0000
    man = (won % 1_0000_0000) // 10_000
    if eok and man:
        return f"{eok}억{man:,}만"
    if eok:
        return f"{eok}억"
    return f"{man:,}만"


def _fmt_won(won: int | None) -> str:
    if won is None:
        return "—"
    sign = "-" if won < 0 else ""
    won  = abs(won)
    eok  = won // 1_0000_0000
    man  = (won % 1_0000_0000) // 10_000
    if eok and man:
        return f"{sign}{eok}억 {man:,}만원"
    if eok:
        return f"{sign}{eok}억원"
    return f"{sign}{man:,}만원"


class TestParsePriceToWon:
    def test_empty_string(self):
        assert _parse_price_to_won("") == 0

    def test_whitespace_only(self):
        assert _parse_price_to_won("   ") == 0

    def test_invalid_text(self):
        assert _parse_price_to_won("abc") == 0

    def test_eok_only(self):
        assert _parse_price_to_won("5억") == 500_000_000

    def test_eok_man(self):
        assert _parse_price_to_won("5억3000만") == 530_000_000

    def test_eok_chun(self):
        assert _parse_price_to_won("5억5천") == 550_000_000

    def test_man_only(self):
        assert _parse_price_to_won("5000만") == 50_000_000

    def test_10eok(self):
        assert _parse_price_to_won("10억") == 1_000_000_000

    def test_float_eok(self):
        assert _parse_price_to_won("2.5억") == 250_000_000

    def test_comma_ignored(self):
        assert _parse_price_to_won("1,000,000,000") == 1_000_000_000


class TestWonToStr:
    def test_zero_returns_empty(self):
        assert _won_to_str(0) == ""

    def test_negative_returns_empty(self):
        assert _won_to_str(-1) == ""

    def test_eok_only(self):
        assert _won_to_str(500_000_000) == "5억"

    def test_eok_and_man(self):
        assert _won_to_str(530_000_000) == "5억3,000만"

    def test_man_only(self):
        assert _won_to_str(50_000_000) == "5,000만"

    def test_roundtrip_5eok(self):
        assert _parse_price_to_won(_won_to_str(500_000_000)) == 500_000_000

    def test_roundtrip_53000man(self):
        original = 530_000_000
        assert _parse_price_to_won(_won_to_str(original)) == original

    def test_roundtrip_10eok(self):
        original = 1_000_000_000
        assert _parse_price_to_won(_won_to_str(original)) == original


class TestFmtWon:
    def test_none_returns_dash(self):
        assert _fmt_won(None) == "—"

    def test_zero_returns_man(self):
        # 0 = 0만원
        assert "만원" in _fmt_won(0) or _fmt_won(0) == "0만원"

    def test_10eok(self):
        assert _fmt_won(1_000_000_000) == "10억원"

    def test_eok_and_man(self):
        assert _fmt_won(1_050_000_000) == "10억 5,000만원"

    def test_man_only(self):
        assert _fmt_won(50_000_000) == "5,000만원"

    def test_negative(self):
        result = _fmt_won(-500_000_000)
        assert result.startswith("-")
        assert "5억원" in result


# ─────────────────────────────────────────
#  listing 연동 로직 단위 테스트
# ─────────────────────────────────────────

class TestListingTypeMap:
    """_LISTING_TYPE_MAP 매핑 규칙 확인 — 소스 파싱"""

    def _read_source(self):
        with open(_SIM_PAGE, encoding="utf-8") as f:
            return f.read()

    def test_residential_mapping_present(self):
        assert "주거용" in self._read_source()

    def test_commercial_mapping_present(self):
        assert "상업용" in self._read_source()

    def test_apply_listing_defaults_func_present(self):
        assert "_apply_listing_defaults" in self._read_source()

    def test_won_to_str_func_present(self):
        assert "_won_to_str" in self._read_source()


# ─────────────────────────────────────────
#  백엔드 연결 smoke
# ─────────────────────────────────────────

class TestBackendSmoke:
    def test_simulation_input_importable(self):
        from schemas.simulation import SimulationInput
        inp = SimulationInput(
            purchase_price=500_000_000,
            loan_amount=250_000_000,
        )
        assert inp.purchase_price == 500_000_000

    def test_run_simulation_importable(self):
        from router import run_simulation
        assert callable(run_simulation)

    def test_run_simulation_dict_mode(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price": 500_000_000,
            "loan_amount":    250_000_000,
        })
        assert state.get("result") is not None
        assert not state.get("error")

    def test_run_simulation_object_mode(self):
        from schemas.simulation import SimulationInput
        from router import run_simulation
        inp   = SimulationInput(purchase_price=500_000_000, loan_amount=200_000_000)
        state = run_simulation(data=inp)
        assert state.get("result") is not None

    def test_run_simulation_returns_report(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price": 700_000_000,
            "loan_amount":    350_000_000,
        })
        assert isinstance(state.get("report"), str)
        assert "부동산 투자 시뮬레이션" in state["report"]

    def test_run_simulation_listing_mode(self):
        """매물 dict 직접 listing 모드"""
        from router import run_simulation
        listing = {"asking_price": 600_000_000, "property_type": "주거용"}
        state   = run_simulation(listing=listing)
        assert state.get("result") is not None
        assert not state.get("error")

    def test_run_simulation_with_jeonse(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price":  700_000_000,
            "loan_amount":     350_000_000,
            "jeonse_deposit":  300_000_000,
        })
        result = state["result"]
        assert result.equity < result.required_cash

    def test_run_simulation_with_monthly_rent(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price": 500_000_000,
            "loan_amount":    250_000_000,
            "monthly_rent":   1_000_000,
        })
        assert state["result"].cash_flow.monthly_rental_income == 1_000_000

    def test_run_simulation_error_propagated(self):
        """유효하지 않은 입력은 error 필드로 반환"""
        from router import run_simulation
        state = run_simulation(data={"purchase_price": -1, "loan_amount": 0})
        assert state.get("error")

    def test_generate_simulation_report_importable(self):
        from services.simulation_service import generate_simulation_report
        assert callable(generate_simulation_report)
