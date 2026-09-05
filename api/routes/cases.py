"""매수 검토 케이스 API."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api import case_db, case_execution_db
from api.deps import get_current_user
from backend.services.market_service import get_region_market_summary
from backend.services.case_comparison_service import compare_case_candidates
from schemas.purchase_case import (
    CaseDecisionCreate, CasePropertyCreate, CasePropertyUpdate, CaseRegionCreate, ChecklistItemUpdate,
    ExecutionPlanUpdate, ExecutionTaskCreate, ExecutionTaskUpdate,
    PurchaseCaseCreate, PurchaseCaseUpdate,
)

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


@router.get("/cases/{case_id}/comparison")
def compare_candidates(
    case_id: int,
    property_id: list[int] | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    case = case_db.get_case(case_id, user["id"])
    if not case:
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    result = compare_case_candidates(case, property_id)
    if len(result["rows"]) < 2:
        raise HTTPException(status_code=422, detail="비교할 후보를 2개 이상 선택해주세요")
    return result


@router.post("/cases/{case_id}/decision")
def select_final_candidate(case_id: int, body: CaseDecisionCreate, user: dict = Depends(get_current_user)):
    result = case_db.select_final_candidate(case_id, body.property_id, user["id"], body.reason)
    if not result:
        raise HTTPException(status_code=404, detail="검토 후보가 없습니다")
    case_execution_db.ensure_execution_plan(case_id, body.property_id, user["id"])
    return result


@router.get("/cases/{case_id}/execution")
def get_execution_plan(case_id: int, user: dict = Depends(get_current_user)):
    result = case_execution_db.get_execution(case_id, user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="검토 케이스가 없습니다")
    return result


@router.patch("/cases/{case_id}/execution")
def update_execution_plan(case_id: int, body: ExecutionPlanUpdate, user: dict = Depends(get_current_user)):
    try:
        result = case_execution_db.update_plan(case_id, user["id"], body.model_dump(exclude_unset=True))
    except ValueError:
        raise HTTPException(status_code=422, detail="잔금 예정일은 계약 예정일보다 빠를 수 없습니다") from None
    if result is None:
        raise HTTPException(status_code=404, detail="최종 선택된 후보 또는 실행 계획이 없습니다")
    return result


@router.post("/cases/{case_id}/execution/tasks", status_code=status.HTTP_201_CREATED)
def add_execution_task(case_id: int, body: ExecutionTaskCreate, user: dict = Depends(get_current_user)):
    result = case_execution_db.add_task(case_id, user["id"], body.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail="실행 계획이 없습니다")
    return result


@router.patch("/cases/{case_id}/execution/tasks/{task_id}")
def update_execution_task(case_id: int, task_id: int, body: ExecutionTaskUpdate, user: dict = Depends(get_current_user)):
    try:
        result = case_execution_db.update_task(case_id, task_id, user["id"], body.model_dump(exclude_unset=True))
    except ValueError:
        raise HTTPException(status_code=422, detail="완료 또는 문제 발견에는 실제 확인자와 확인 결과가 필요합니다") from None
    if result is None:
        raise HTTPException(status_code=404, detail="실행 작업이 없습니다")
    return result


@router.delete("/cases/{case_id}/execution/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_execution_task(case_id: int, task_id: int, user: dict = Depends(get_current_user)):
    try:
        result = case_execution_db.delete_task(case_id, task_id, user["id"])
    except ValueError:
        raise HTTPException(status_code=422, detail="시스템 기본 작업은 삭제할 수 없습니다. 해당 없음으로 변경해주세요") from None
    if not result:
        raise HTTPException(status_code=404, detail="실행 작업이 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.patch("/cases/{case_id}/properties/{property_id}")
def update_property(case_id: int, property_id: int, body: CasePropertyUpdate, user: dict = Depends(get_current_user)):
    item = case_db.update_property(case_id, property_id, user["id"], body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail="후보 부동산이 없습니다")
    return item


@router.patch("/cases/{case_id}/properties/{property_id}/checklist/{checklist_id}")
def update_checklist(case_id: int, property_id: int, checklist_id: int, body: ChecklistItemUpdate, user: dict = Depends(get_current_user)):
    item = case_db.update_checklist(case_id, property_id, checklist_id, user["id"], body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(status_code=404, detail="검토 항목이 없습니다")
    return item


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
