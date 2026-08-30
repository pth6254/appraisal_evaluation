"""매수 검토 케이스 API."""
from fastapi import APIRouter, Depends, HTTPException, Response, status

from api import case_db
from api.deps import get_current_user
from backend.services.market_service import get_region_market_summary
from schemas.purchase_case import CasePropertyCreate, CaseRegionCreate, PurchaseCaseCreate, PurchaseCaseUpdate

router = APIRouter(tags=["purchase-cases"])


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_case(body: PurchaseCaseCreate, user: dict = Depends(get_current_user)):
    return case_db.create_case(user["id"], body.model_dump())


@router.get("/cases")
def list_cases(user: dict = Depends(get_current_user)):
    return {"items": case_db.list_cases(user["id"])}


@router.get("/cases/{case_id}")
def get_case(case_id: int, user: dict = Depends(get_current_user)):
    case = case_db.get_case(case_id, user["id"])
    if not case:
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    return case


@router.patch("/cases/{case_id}")
def update_case(case_id: int, body: PurchaseCaseUpdate, user: dict = Depends(get_current_user)):
    case = case_db.update_case(case_id, user["id"], body.model_dump(exclude_unset=True))
    if not case:
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    return case


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: int, user: dict = Depends(get_current_user)):
    if not case_db.delete_case(case_id, user["id"]):
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cases/{case_id}/properties", status_code=status.HTTP_201_CREATED)
def add_property(case_id: int, body: CasePropertyCreate, user: dict = Depends(get_current_user)):
    try:
        item = case_db.add_property(case_id, user["id"], body.model_dump())
    except LookupError:
        raise HTTPException(status_code=404, detail="연결할 시세추정 이력이 없습니다") from None
    if not item:
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    return item


@router.delete("/cases/{case_id}/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(case_id: int, property_id: int, user: dict = Depends(get_current_user)):
    deleted = case_db.delete_property(case_id, property_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="후보 부동산이 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cases/{case_id}/regions", status_code=status.HTTP_201_CREATED)
def add_region(case_id: int, body: CaseRegionCreate, user: dict = Depends(get_current_user)):
    # 통계를 조회하기 전에 소유권을 확인해야 타인의 케이스 존재 여부와 작업을 모두 숨길 수 있다.
    if not case_db.get_case(case_id, user["id"]):
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    summary = get_region_market_summary(
        region_code=body.region_code, property_type=body.property_type,
        months=body.months, budget_max_won=body.budget_max_won,
    )
    market_item = next(
        (item for item in summary.get("items", []) if item["region_code"] == body.region_code), None
    )
    if not market_item:
        raise HTTPException(status_code=422, detail="해당 지역에 저장할 수집 실거래 통계가 없습니다")
    period = summary.get("period") or {}
    try:
        item = case_db.add_region(case_id, user["id"], {
            "region_code": body.region_code, "source": body.source,
            "property_type": body.property_type, "budget_max_won": body.budget_max_won,
            "period_from": period.get("from"), "period_to": period.get("to"),
            "stats_snapshot": market_item,
        })
    except LookupError:
        raise HTTPException(status_code=404, detail="행정구역을 찾을 수 없습니다") from None
    if not item:
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    return item


@router.delete("/cases/{case_id}/regions/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_region(case_id: int, region_id: int, user: dict = Depends(get_current_user)):
    if not case_db.delete_region(case_id, region_id, user["id"]):
        raise HTTPException(status_code=404, detail="관심 지역이 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
