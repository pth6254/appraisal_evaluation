"""단지 추천 연결에서 상한·최소 면적·후속 조건과 모델 재작성 방지를 검증한다."""
import pytest
from tests.test_market_explorer import client
from tests.test_concierge_validation import route


def test_followup_recommends_complexes_without_writer(client, monkeypatch):
    from backend import model_factory
    from backend.services import complex_recommend_service as service
    samples = []
    for name, area, price in [('조건충족',84,70000),('상한초과',84,85000),('면적미달',40,30000)]:
        samples.extend([{'apt_name':name,'dong':'역삼동','area_sqm':area,'price':price,
            'per_sqm':price/area,'deal_year':'2026','deal_month':'08','year_built':'2020'}]*2)
    monkeypatch.setattr(service,'_load_samples',lambda *_:samples)
    monkeypatch.setattr(service,'_apply_time_adjustment',lambda samples,*_: (samples,None))
    monkeypatch.setattr(model_factory,'get_llm',lambda:pytest.fail('단지 결과를 LLM으로 재작성하면 안 된다'))
    route(monkeypatch,{'intent':'select_property','criteria':{'region_name':'강남구',
        'property_type':'apartment','transaction_type':'purchase','budget_max_won':800000000,'area_min_sqm':59}})
    first=client.post('/api/concierge/messages',json={'message':'강남구 아파트 매매 8억 59제곱 이상 단지 추천'}).json()
    assert first['status']=='completed'
    assert [r['complex_name'] for r in first['data']['results']]==['조건충족']
    assert '70,000만원' in first['answer']
    assert '호가가 아닙니다' in first['answer']
    route(monkeypatch,{'intent':'select_property','criteria':{'budget_max_won':600000000}})
    second=client.post('/api/concierge/messages',json={'message':'6억 이하로', 'conversation_id':first['conversation_id']}).json()
    assert second['status']=='completed' and second['data']['results']==[]
    assert second['criteria']['area_min_sqm']==59
    assert second['criteria']['region_code']=='1168000000'


@pytest.mark.parametrize('criteria,status,missing',[
    ({},'needs_input','region'),
    ({'region_name':'서울'},'needs_input','region_code'),
    ({'region_name':'강남구'},'needs_input','transaction_type'),
    ({'region_name':'강남구','property_type':'apartment','transaction_type':'lease'},'not_available',None),
    ({'region_name':'강남구','property_type':'apartment','transaction_type':'purchase','budget_max_won':0},'completed',None),
])
def test_missing_or_unsupported_does_not_load_transactions(client,monkeypatch,criteria,status,missing):
    from backend.services import complex_recommend_service as service
    monkeypatch.setattr(service,'recommend_complexes',lambda *_args,**_kwargs:pytest.fail('불완전 조건으로 조회'))
    route(monkeypatch,{'intent':'select_property','criteria':criteria})
    result=client.post('/api/concierge/messages',json={'message':'구체적인 단지 추천해줘'}).json()
    assert result['status']==status
    assert '연결 준비 중' not in result['answer']
    if missing:
        assert missing in result['missing_fields']
