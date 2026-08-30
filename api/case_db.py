"""매수 검토 케이스 저장소. 모든 공개 함수는 user_id로 소유자를 제한한다."""
from __future__ import annotations

from sqlalchemy import delete, func, select

from db.base import session_scope
from db.models import CaseProperty, CaseRegion, HistoryRecord, LegalRegion, PurchaseCase
from db.models import _now_str


def _case_dict(case: PurchaseCase, property_count: int = 0) -> dict:
    return {
        "id": case.id, "title": case.title, "status": case.status, "purpose": case.purpose,
        "budget_min": case.budget_min, "budget_max": case.budget_max,
        "target_regions": case.target_regions or [], "notes": case.notes,
        "created": case.created, "updated": case.updated, "property_count": property_count,
    }


def create_case(user_id: int, data: dict) -> dict:
    with session_scope() as session:
        case = PurchaseCase(user_id=user_id, **data)
        session.add(case)
        session.flush()
        return _case_dict(case)


def list_cases(user_id: int) -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            select(PurchaseCase, func.count(CaseProperty.id))
            .outerjoin(CaseProperty, CaseProperty.case_id == PurchaseCase.id)
            .where(PurchaseCase.user_id == user_id)
            .group_by(PurchaseCase.id)
            .order_by(PurchaseCase.updated.desc(), PurchaseCase.id.desc())
        ).all()
        return [_case_dict(case, count) for case, count in rows]


def get_case(case_id: int, user_id: int) -> dict | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        properties = session.scalars(
            select(CaseProperty).where(CaseProperty.case_id == case.id).order_by(CaseProperty.created, CaseProperty.id)
        ).all()
        regions = session.scalars(
            select(CaseRegion).where(CaseRegion.case_id == case.id).order_by(CaseRegion.created, CaseRegion.id)
        ).all()
        history_ids = [item.history_id for item in properties if item.history_id]
        histories = {}
        if history_ids:
            histories = {row.id: row for row in session.scalars(
                select(HistoryRecord).where(HistoryRecord.id.in_(history_ids), HistoryRecord.user_id == user_id)
            )}
        result = _case_dict(case, len(properties))
        result["properties"] = [_property_dict(item, histories.get(item.history_id)) for item in properties]
        result["regions"] = [_region_dict(item) for item in regions]
        return result


def update_case(case_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        for key, value in data.items():
            setattr(case, key, value)
        case.updated = _now_str()
        session.flush()
        return _case_dict(case, session.scalar(select(func.count()).select_from(CaseProperty).where(CaseProperty.case_id == case.id)) or 0)


def delete_case(case_id: int, user_id: int) -> bool:
    with session_scope() as session:
        result = session.execute(delete(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        return bool(result.rowcount)


def add_property(case_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        history = None
        history_id = data.get("history_id")
        if history_id:
            history = session.scalar(select(HistoryRecord).where(HistoryRecord.id == history_id, HistoryRecord.user_id == user_id))
            if not history:
                raise LookupError("history_not_found")
        item = CaseProperty(case_id=case.id, **data)
        session.add(item)
        case.updated = _now_str()
        session.flush()
        return _property_dict(item, history)


def delete_property(case_id: int, property_id: int, user_id: int) -> bool | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        result = session.execute(delete(CaseProperty).where(CaseProperty.id == property_id, CaseProperty.case_id == case.id))
        if result.rowcount:
            case.updated = _now_str()
        return bool(result.rowcount)


def add_region(case_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        region = session.scalar(select(LegalRegion).where(
            LegalRegion.code == data["region_code"], LegalRegion.is_active.is_(True)
        ))
        if not region:
            raise LookupError("region_not_found")
        existing = session.scalar(select(CaseRegion).where(
            CaseRegion.case_id == case.id, CaseRegion.region_code == region.code
        ))
        if existing:
            return _region_dict(existing)
        item = CaseRegion(case_id=case.id, region_name=region.full_name, **data)
        session.add(item)
        if region.full_name not in (case.target_regions or []):
            case.target_regions = [*(case.target_regions or []), region.full_name]
        case.updated = _now_str()
        session.flush()
        return _region_dict(item)


def delete_region(case_id: int, region_id: int, user_id: int) -> bool | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        item = session.scalar(select(CaseRegion).where(
            CaseRegion.id == region_id, CaseRegion.case_id == case.id
        ))
        if not item:
            return False
        session.delete(item)
        case.target_regions = [name for name in (case.target_regions or []) if name != item.region_name]
        case.updated = _now_str()
        return True


def _property_dict(item: CaseProperty, history: HistoryRecord | None = None) -> dict:
    appraisal = None
    if history:
        analysis = (history.result or {}).get("analysis_result") or {}
        appraisal = {
            "history_id": history.id, "query": history.query,
            "estimated_value": analysis.get("estimated_value") or history.result.get("estimated_value"),
            "valuation_verdict": analysis.get("valuation_verdict") or history.result.get("valuation_verdict"),
            "created": history.created,
        }
    return {
        "id": item.id, "case_id": item.case_id, "name": item.name, "address": item.address,
        "category": item.category, "asking_price": item.asking_price, "area_sqm": item.area_sqm,
        "legal_region_code": item.legal_region_code, "source": item.source, "status": item.status,
        "notes": item.notes, "history_id": item.history_id, "appraisal": appraisal,
        "created": item.created, "updated": item.updated,
    }


def _region_dict(item: CaseRegion) -> dict:
    return {
        "id": item.id, "case_id": item.case_id,
        "region_code": item.region_code, "region_name": item.region_name,
        "source": item.source, "property_type": item.property_type,
        "budget_max_won": item.budget_max_won,
        "period_from": item.period_from, "period_to": item.period_to,
        "stats_snapshot": item.stats_snapshot or {}, "created": item.created,
    }
