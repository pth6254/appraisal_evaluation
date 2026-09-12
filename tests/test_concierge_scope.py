"""동 단위 집계와 대화 조건 유지, 공식 코드 우선 매칭을 검증한다."""
import time
from types import SimpleNamespace

from tests.test_market_explorer import client
from tests.test_concierge_validation import route
from backend.graphs.concierge_graph import execute_node, explain_node


def test_dong_scope_completed_and_keeps_budget(client, monkeypatch):
    from backend import model_factory
    monkeypatch.setattr(model_factory, 'get_llm', lambda: SimpleNamespace(invoke=lambda _: SimpleNamespace(content="수집된 실거래를 확인했습니다.")))
    from db.base import session_scope
    from db.models import LegalRegion
    with session_scope() as session:
        session.add(LegalRegion(code="1168010100", parent_code="1168000000", sido_code="11",
            sigungu_code="680", eup_myeon_dong_code="101", ri_code="00", name="역삼동",
            full_name="서울특별시 강남구 역삼동", level="eup_myeon_dong", depth=3,
            lawd_code="11680", resident_code="", cadastral_code="", sort_order=1,
            remarks="", is_active=True, synced_at=time.time()))
    state = route(monkeypatch, {"intent": "find_region", "criteria": {"region_name": "역삼동",
        "property_type": "apartment", "transaction_type": "purchase", "budget_max_won": 800000000}})
    output = explain_node(execute_node(state))
    assert output["tool_result"].status == "completed"
    assert output["tool_result"].data["scope"]["code"] == "1168010100"
    assert output["decision"].criteria.budget_max_won == 800000000
    first = client.post('/api/concierge/messages', json={"message": "역삼동 아파트 매매 8억 추천"}).json()
    assert first['status'] == 'completed'
    # 동에서 구로 범위를 넓혀도 예산은 유지된다.
    route(monkeypatch, {"intent": "find_region", "criteria": {"region_name": "강남구"}})
    second = client.post('/api/concierge/messages', json={"message": "강남구로", "conversation_id": first['conversation_id']}).json()
    assert second['status'] == 'completed'
    assert second['criteria']['budget_max_won'] == 800000000


def test_dong_matching_and_saved_snapshot(client, monkeypatch):
    from db.base import session_scope
    from db.models import LegalRegion, Transaction
    with session_scope() as session:
        for code, parent, name in [("1168010100", "1168000000", "역삼동"),
                                   ("1168010200", "1168000000", "논현동"),
                                   ("1165010100", "1165000000", "역삼동")]:
            session.add(LegalRegion(code=code, parent_code=parent, sido_code="11",
                sigungu_code=code[2:5], eup_myeon_dong_code=code[5:8], ri_code="00", name=name,
                full_name=f"서울특별시 {'강남구' if code[2:5] == '680' else '서초구'} {name}",
                level="eup_myeon_dong", depth=3, lawd_code=code[:5], resident_code="",
                cadastral_code="", sort_order=1, remarks="", is_active=True, synced_at=time.time()))
        for code, dong, price, cancelled, endpoint, lawd in [
            ("1168010100", "틀린이름", 60000, False, "RTMSDataSvcAptTrade", "11680"),
            (None, " 역삼동 ", 100000, False, "RTMSDataSvcAptTrade", "11680"),
            ("1168010200", "역삼동", 30000, False, "RTMSDataSvcAptTrade", "11680"),
            (None, "역삼동", 1, True, "RTMSDataSvcAptTrade", "11680"),
            (None, "역삼동", 2, False, "RTMSDataSvcLandTrade", "11680"),
            (None, "역삼동", 3, False, "RTMSDataSvcAptTrade", "11650"),
            (None, "미확인동", 4, False, "RTMSDataSvcAptTrade", "11680"),
        ]:
            session.add(Transaction(endpoint=endpoint, category="주거용", lawd_cd=lawd,
                deal_ym="202608", price=price, area_sqm=84, per_sqm=price/84, apt_name="검증단지",
                dong=dong, bjdong_code=code, is_cancelled=cancelled))
    root = "/api/market/regions/summary"
    params = {"region_code": "1168000000", "group_level": "eup_myeon_dong",
              "property_type": "apartment", "budget_max": 80000}
    response = client.get(root, params=params)
    assert response.status_code == 200
    items = {r['region_code']: r for r in response.json()['items']}
    assert set(items) == {"1168010100", "1168010200"}
    assert items['1168010100']['deal_count'] == 2
    assert items['1168010100']['median_price'] == 80000
    assert items['1168010100']['budget_fit_ratio'] == .5
    assert items['1168010200']['deal_count'] == 1
    single = client.get(root, params={**params, 'region_code': '1168010100'}).json()
    assert single['items'] == [items['1168010100']]
    for level in ['eup_myeon_dong', 'eupmyeondong']:
        assert len(client.get('/api/market/regions', params={'level': level, 'parent_code': '1168000000'}).json()['items']) == 2
    case_id = client.post('/api/cases', json={'title': '동 검토'}).json()['id']
    saved = client.post(f'/api/cases/{case_id}/regions', json={
        'region_code': '1168010100', 'property_type': 'apartment', 'budget_max_won': 800000000})
    assert saved.status_code == 201
    assert saved.json()['stats_snapshot']['median_price'] == 80000
    from backend.services import complex_recommend_service as service
    monkeypatch.setattr(service, '_load_samples', lambda *_: [
        {'bjdong_code': c, 'dong': d, 'price': p, 'area_sqm': 84, 'per_sqm': p/84,
         'apt_name': '역삼단지' if c == '1168010100' else '다른단지',
         'is_cancelled': cancelled, 'deal_year': '2026', 'deal_month': '08'}
        for c, d, p, cancelled in [('1168010100', '역삼동', 60000, False),
                                  ('1168010100', '역삼동', 100000, False),
                                  ('1168010100', '역삼동', 1, True),
                                  ('1168010200', '역삼동', 30000, False)]])
    monkeypatch.setattr(service, '_apply_time_adjustment', lambda samples, *_: (samples, None))
    result = service.recommend_complexes('무시할 이름', region_code='1168010100')
    assert len(result['results']) == 1
    assert result['results'][0]['deal_count'] == 2
    assert result['results'][0]['avg_price'] == 80000
