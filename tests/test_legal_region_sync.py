"""전국 10자리 법정동코드 동기화 단위 테스트."""
from __future__ import annotations

import json

import pytest

from backend.tools import sync_legal_regions as sync


def _row(
    code: str,
    full_name: str,
    parent: str = "0000000000",
    *,
    sido: str | None = None,
    sgg: str | None = None,
    umd: str | None = None,
    ri: str | None = None,
) -> dict:
    return {
        "region_cd": code,
        "sido_cd": sido or code[:2],
        "sgg_cd": sgg or code[2:5],
        "umd_cd": umd or code[5:8],
        "ri_cd": ri or code[8:10],
        "locatjumin_cd": code,
        "locatjijuk_cd": code,
        "locatadd_nm": full_name,
        "locat_order": 1,
        "locat_rm": "",
        "locathigh_cd": parent,
        "locallow_nm": full_name.split()[-1],
        "adpt_de": "20260101",
    }


def test_prepare_records_keeps_real_parent_depth():
    """수원시→장안구처럼 시군구 코드 레벨이 중첩돼도 실제 깊이를 보존한다."""
    rows = [
        _row("4100000000", "경기도", sido="41", sgg="000", umd="000", ri="00"),
        _row("4111000000", "경기도 수원시", "4100000000", umd="000", ri="00"),
        _row("4111100000", "경기도 수원시 장안구", "4111000000", umd="000", ri="00"),
        _row("4111112900", "경기도 수원시 장안구 영화동", "4111100000", ri="00"),
    ]

    records = sync.prepare_records(rows, synced_at=123.0)
    by_code = {record["code"]: record for record in records}

    assert by_code["4100000000"]["depth"] == 1
    assert by_code["4111000000"]["depth"] == 2
    assert by_code["4111100000"]["depth"] == 3
    assert by_code["4111112900"]["depth"] == 4
    assert by_code["4111100000"]["level"] == "sigungu"
    assert by_code["4111112900"]["level"] == "eup_myeon_dong"
    assert by_code["4111112900"]["lawd_code"] == "41111"


def test_parse_ri_and_dates():
    row = _row(
        "4182025021",
        "경기도 가평군 가평읍 읍내리",
        "4182025000",
        sgg="820",
        umd="250",
        ri="21",
    )
    record = sync.parse_row(row, synced_at=1.5)

    assert record["level"] == "ri"
    assert record["name"] == "읍내리"
    assert record["effective_date"] == "20260101"
    assert record["abolished_date"] is None
    assert record["is_active"] is True


def test_invalid_code_is_rejected():
    with pytest.raises(ValueError, match="10자리"):
        sync.parse_row(_row("123", "잘못된 지역"), synced_at=1.0)


class _Response:
    def __init__(self, payload: dict):
        self.content = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, pages: list[list[dict]]):
        self.pages = pages
        self.calls: list[int] = []

    def get(self, _url, *, params, timeout):
        assert timeout == 30
        page = int(params["pageNo"])
        self.calls.append(page)
        all_count = sum(len(rows) for rows in self.pages)
        payload = {
            "StanReginCd": [
                {"head": [
                    {"totalCount": all_count},
                    {"numOfRows": str(params["numOfRows"]), "pageNo": str(page)},
                    {"RESULT": {"resultCode": "INFO-0", "resultMsg": "정상"}},
                ]},
                {"row": self.pages[page - 1]},
            ]
        }
        return _Response(payload)


def test_fetch_all_paginates_and_decodes_utf8():
    pages = [
        [_row("1100000000", "서울특별시", sido="11", sgg="000", umd="000", ri="00")],
        [_row("1111000000", "서울특별시 종로구", "1100000000", umd="000", ri="00")],
    ]
    http = _Session(pages)

    rows = sync.fetch_all("test-key", page_size=1, http=http)

    assert http.calls == [1, 2]
    assert [row["locatadd_nm"] for row in rows] == ["서울특별시", "서울특별시 종로구"]


def test_duplicate_code_is_rejected():
    row = _row("1100000000", "서울특별시", sido="11", sgg="000", umd="000", ri="00")
    with pytest.raises(ValueError, match="중복"):
        sync.prepare_records([row, row], synced_at=1.0)


def test_missing_parent_is_rejected():
    row = _row("1111000000", "서울특별시 종로구", "1199999999", umd="000", ri="00")
    with pytest.raises(ValueError, match="상위코드"):
        sync.prepare_records([row], synced_at=1.0)
