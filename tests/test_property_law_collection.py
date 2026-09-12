"""법령 API의 계층 본문 보존과 잘못된 수집 결과의 차단을 검증한다."""
import json
from copy import deepcopy

import pytest

from backend.tools.collect_property_laws import LawClient, main, normalize_law, redact_auth, save_law


@pytest.fixture
def law():
    match = {"법령명한글": "주택임대차보호법", "법령ID": "001", "법령일련번호": "123", "시행일자": "20260101"}
    payload = {"법령": {"기본정보": {"법령명_한글": "주택임대차보호법", "시행일자": "20260101"},
        "조문": {"조문단위": {"조문번호": "3", "조문가지번호": "2", "조문내용": "긴 본문" * 400,
            "항": {"항내용": "항 본문", "호": [{"호내용": "호 본문", "목": {"목내용": "목 본문"}}]}}},
        "부칙": {"부칙단위": {"부칙내용": "경과조치"}}, "별표": {"별표단위": {"별표제목": "별표"}}}}
    return match, payload


def test_preserves_nested_text_branches_and_supplements(law):
    match, payload = law
    record = normalize_law(payload, match, "2026-09-10T10:00:00+09:00")
    article = record["articles"][0]
    assert len(article["text"]) > 800
    assert article["text"].endswith("항 본문\n호 본문\n목 본문")
    assert article["branch_number"] == "2"
    assert record["supplementary"] == payload["법령"]["부칙"]
    assert record["annexes"] == payload["법령"]["별표"]


@pytest.mark.parametrize("field,value", [("법령명_한글", "다른 법"), ("시행일자", "20990101"), ("시행일자", "")])
def test_rejects_wrong_or_future_law(law, field, value):
    match, payload = law
    payload["법령"]["기본정보"][field] = value
    with pytest.raises(ValueError):
        normalize_law(payload, match, "2026-09-10T00:00:00+09:00")


def test_repeated_collection_does_not_duplicate_snapshot(tmp_path, law):
    match, payload = law
    first = save_law(tmp_path, payload, match, "2026-09-10T10:00:00+09:00")
    second = save_law(tmp_path, payload, match, "2026-09-11T10:00:00+09:00")
    assert first["directory"] == second["directory"]
    assert len(list(tmp_path.iterdir())) == 1
    assert json.loads((tmp_path / first["directory"] / "raw.json").read_text()) == payload
    changed = deepcopy(payload)
    changed["법령"]["조문"]["조문단위"]["조문내용"] = "변경된 조문"
    assert save_law(tmp_path, changed, match, "2026-09-11T10:00:00+09:00")["directory"] != first["directory"]


def test_auth_is_not_saved():
    cleaned = redact_auth({"OC": "private", "link": "https://law.go.kr/?OC=private&ID=1"})
    assert "private" not in json.dumps(cleaned)


def test_pagination_exact_match_and_pinned_version(monkeypatch, law):
    match, payload = law
    client = LawClient("test-fixture")
    calls = []
    def get(endpoint, **params):
        calls.append((endpoint, params))
        if endpoint == "lawService.do":
            return payload
        return {"LawSearch": {"totalCnt": 101, "law": {"법령명한글": "다른 법"} if params["page"] == 1 else match}}
    monkeypatch.setattr(client, "get", get)
    assert client.fetch("주택임대차보호법") == (match, payload)
    assert calls[0][1]["nw"] == 3
    assert calls[-1] == ("lawService.do", {"MST": "123", "efYd": "20260101"})


def test_missing_auth_fails_before_network_or_files(monkeypatch, tmp_path):
    import backend.tools.collect_property_laws as collector
    monkeypatch.delenv("LAW_OC_KEY", raising=False)
    monkeypatch.delenv("LAW_API_KEY", raising=False)
    monkeypatch.setattr(collector, "load_dotenv", lambda _: None)
    assert main(["--output", str(tmp_path / "output")]) == 2
    assert not (tmp_path / "output").exists()
