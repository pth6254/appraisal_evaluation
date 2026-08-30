from backend.tools.ingest_transactions import _endpoints_for, _month_range, _recent_months
from xml.etree import ElementTree as ET
from price_engine import _parse_items


def test_month_range_crosses_year():
    assert _month_range("202511", "202602") == ["202511", "202512", "202601", "202602"]


def test_duplicate_source_endpoint_is_collected_once():
    endpoints = _endpoints_for(["상업용", "업무용"])
    assert len(endpoints) == 1


def test_recent_month_count():
    months = _recent_months(12)
    assert len(months) == 12
    assert months == sorted(months)


def test_parser_builds_legal_dong_code_from_request_region():
    item = ET.fromstring(
        "<item><dealAmount>100,000</dealAmount><excluUseAr>50</excluUseAr>"
        "<umdCd>103</umdCd><umdNm>역삼동</umdNm></item>"
    )
    row = _parse_items([item], "주거용", "아파트", "11680")[0]
    assert row["bjdong_code"] == "1168010300"
