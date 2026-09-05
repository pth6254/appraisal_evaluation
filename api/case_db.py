"""매수 검토 케이스 저장소. 모든 공개 함수는 user_id로 소유자를 제한한다."""
from __future__ import annotations

from sqlalchemy import delete, func, select

from db.base import session_scope
from db.models import (
    CandidateAnalysis, CandidateChecklistItem, CaseProperty, CaseRegion,
    HistoryRecord, LegalRegion, PurchaseCase,
)
from db.models import _now_str
from backend.services.analysis_freshness import analysis_freshness, expiry_for
from backend.services.candidate_next_actions import candidate_next_actions


def _case_dict(case: PurchaseCase, property_count: int = 0) -> dict:
    return {
        "id": case.id, "title": case.title, "status": case.status, "purpose": case.purpose,
        "budget_min": case.budget_min, "budget_max": case.budget_max,
        "target_regions": case.target_regions or [], "notes": case.notes,
        "selected_property_id": case.selected_property_id,
        "decision_reason": case.decision_reason or "", "decided_at": case.decided_at,
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
        property_ids = [item.id for item in properties]
        analyses_by_property: dict[int, list] = {item.id: [] for item in properties}
        checklist_by_property: dict[int, list] = {item.id: [] for item in properties}
        if property_ids:
            for row in session.scalars(select(CandidateAnalysis).where(CandidateAnalysis.property_id.in_(property_ids))):
                analyses_by_property[row.property_id].append(_analysis_dict(row))
            for row in session.scalars(select(CandidateChecklistItem).where(
                CandidateChecklistItem.property_id.in_(property_ids)
            ).order_by(CandidateChecklistItem.sort_order, CandidateChecklistItem.id)):
                checklist_by_property[row.property_id].append(_checklist_dict(row))
        result = _case_dict(case, len(properties))
        result["properties"] = [
            _property_dict(item, histories.get(item.history_id), analyses_by_property[item.id], checklist_by_property[item.id])
            for item in properties
        ]
        result["regions"] = [_region_dict(item) for item in regions]
        for candidate in result["properties"]:
            candidate["next_actions"] = candidate_next_actions(result, candidate)
        all_checks = [check for checks in checklist_by_property.values() for check in checks]
        done = sum(check["status"] == "done" for check in all_checks)
        result["workspace"] = {
            "checklist_total": len(all_checks), "checklist_done": done,
            "warning_count": sum(check["status"] == "warning" for check in all_checks),
            "blocked_count": sum(check["status"] == "blocked" for check in all_checks),
            "progress_percent": round(done / len(all_checks) * 100) if all_checks else 0,
        }
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
        session.flush()
        for order, (category, title) in enumerate([
            ("price", "적정가격 확인"), ("funding", "자금 조건 입력 필요"),
            ("rights", "권리서류 업로드 필요"), ("site", "현장 상태 확인"),
            ("contract", "계약 조건 확인"),
        ]):
            linked_appraisal = bool(history and category == "price")
            session.add(CandidateChecklistItem(
                case_id=case.id, property_id=item.id, category=category,
                title=title, sort_order=order, status="done" if linked_appraisal else "todo",
                source="appraisal" if linked_appraisal else "system",
                evidence=f"시세추정 이력 #{history.id} 연결" if linked_appraisal else "",
                completed_at=_now_str() if linked_appraisal else None,
            ))
        if history:
            analysis_result = (history.result or {}).get("analysis_result") or {}
            session.add(CandidateAnalysis(
                case_id=case.id, property_id=item.id, analysis_type="appraisal",
                reference_id=history.id, analyzed_at=history.created,
                expires_at=expiry_for("appraisal", history.created),
                summary={
                    "history_id": history.id,
                    "estimated_value": analysis_result.get("estimated_value") or history.result.get("estimated_value"),
                    "valuation_verdict": analysis_result.get("valuation_verdict") or history.result.get("valuation_verdict"),
                },
            ))
        case.updated = _now_str()
        session.flush()
        checks = session.scalars(select(CandidateChecklistItem).where(CandidateChecklistItem.property_id == item.id).order_by(CandidateChecklistItem.sort_order)).all()
        analyses = session.scalars(select(CandidateAnalysis).where(CandidateAnalysis.property_id == item.id)).all()
        return _property_dict(item, history, [_analysis_dict(value) for value in analyses], [_checklist_dict(check) for check in checks])


def update_property(case_id: int, property_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        item = session.scalar(select(CaseProperty).where(CaseProperty.id == property_id, CaseProperty.case_id == case.id))
        if not item:
            return None
        for key, value in data.items():
            setattr(item, key, value)
        item.updated = case.updated = _now_str()
        session.flush()
        return _property_dict(item)


def select_final_candidate(case_id: int, property_id: int, user_id: int, reason: str) -> dict | None:
    """최종 후보와 선택 근거를 같은 트랜잭션에서 저장한다."""
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(
            PurchaseCase.id == case_id, PurchaseCase.user_id == user_id,
        ))
        if not case:
            return None
        selected = session.scalar(select(CaseProperty).where(
            CaseProperty.id == property_id, CaseProperty.case_id == case.id,
        ))
        if not selected:
            return None
        now = _now_str()
        properties = session.scalars(select(CaseProperty).where(CaseProperty.case_id == case.id)).all()
        for item in properties:
            if item.id == selected.id:
                item.status = "selected"
            elif item.status == "selected":
                item.status = "shortlisted"
            item.updated = now
        case.selected_property_id = selected.id
        case.decision_reason = reason
        case.decided_at = now
        case.status = "decided"
        case.updated = now
        session.flush()
        return _case_dict(case, len(properties))


def update_checklist(case_id: int, property_id: int, checklist_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = session.scalar(select(PurchaseCase).where(PurchaseCase.id == case_id, PurchaseCase.user_id == user_id))
        if not case:
            return None
        check = session.scalar(select(CandidateChecklistItem).where(
            CandidateChecklistItem.id == checklist_id,
            CandidateChecklistItem.property_id == property_id,
            CandidateChecklistItem.case_id == case.id,
        ))
        if not check:
            return None
        check.status = data["status"]
        if data.get("evidence") is not None:
            check.evidence = data["evidence"]
        check.completed_at = _now_str() if check.status == "done" else None
        check.updated = case.updated = _now_str()
        session.flush()
        return _checklist_dict(check)


def validate_candidate(case_id: int, property_id: int, user_id: int) -> bool:
    with session_scope() as session:
        return session.scalar(select(CaseProperty.id).join(
            PurchaseCase, PurchaseCase.id == CaseProperty.case_id
        ).where(
            PurchaseCase.id == case_id, PurchaseCase.user_id == user_id,
            CaseProperty.id == property_id, CaseProperty.case_id == case_id,
        )) is not None


def link_appraisal(case_id: int, property_id: int, history_id: int, user_id: int, result: dict) -> bool:
    """분석 완료 시 후보·분석·가격 체크 항목을 하나의 트랜잭션으로 갱신한다."""
    with session_scope() as session:
        item = session.scalar(select(CaseProperty).join(
            PurchaseCase, PurchaseCase.id == CaseProperty.case_id
        ).where(
            PurchaseCase.id == case_id, PurchaseCase.user_id == user_id,
            CaseProperty.id == property_id, CaseProperty.case_id == case_id,
        ))
        if not item:
            return False
        now = _now_str()
        analysis_result = result.get("analysis_result") or {}
        estimated = analysis_result.get("estimated_value") or result.get("estimated_value")
        verdict = analysis_result.get("valuation_verdict") or result.get("valuation_verdict")
        summary = {"history_id": history_id, "estimated_value": estimated, "valuation_verdict": verdict}
        analysis = session.scalar(select(CandidateAnalysis).where(
            CandidateAnalysis.property_id == property_id, CandidateAnalysis.analysis_type == "appraisal"
        ))
        if analysis:
            analysis.reference_id, analysis.status, analysis.summary = history_id, "completed", summary
            analysis.analyzed_at = analysis.updated = now
            analysis.expires_at = expiry_for("appraisal", now)
        else:
            session.add(CandidateAnalysis(case_id=case_id, property_id=property_id, analysis_type="appraisal", reference_id=history_id, summary=summary, analyzed_at=now, expires_at=expiry_for("appraisal", now)))
        item.history_id, item.updated = history_id, now
        check = session.scalar(select(CandidateChecklistItem).where(
            CandidateChecklistItem.property_id == property_id, CandidateChecklistItem.category == "price"
        ))
        if check:
            check.status = "done"
            check.evidence = f"시세추정 이력 #{history_id} 연결"
            check.completed_at = check.updated = now
        case = session.get(PurchaseCase, case_id)
        case.updated = now
        return True


def link_candidate_analysis(case_id: int, property_id: int, user_id: int, analysis_type: str,
                            summary: dict, checklist_status: str = "done", evidence: str = "") -> bool:
    """실제로 완료된 계산·문서 분석만 후보에 연결한다."""
    category = {"simulation": "funding", "rights": "rights"}.get(analysis_type)
    if not category:
        raise ValueError("지원하지 않는 후보 분석 유형")
    with session_scope() as session:
        item = session.scalar(select(CaseProperty).join(
            PurchaseCase, PurchaseCase.id == CaseProperty.case_id
        ).where(
            PurchaseCase.id == case_id, PurchaseCase.user_id == user_id,
            CaseProperty.id == property_id, CaseProperty.case_id == case_id,
        ))
        if not item:
            return False
        now = _now_str()
        analysis = session.scalar(select(CandidateAnalysis).where(
            CandidateAnalysis.property_id == property_id, CandidateAnalysis.analysis_type == analysis_type,
        ))
        if analysis:
            analysis.status, analysis.summary = "completed", summary
            analysis.analyzed_at = analysis.updated = now
            analysis.expires_at = expiry_for(analysis_type, now)
        else:
            session.add(CandidateAnalysis(case_id=case_id, property_id=property_id,
                        analysis_type=analysis_type, status="completed", summary=summary, analyzed_at=now,
                        expires_at=expiry_for(analysis_type, now)))
        check = session.scalar(select(CandidateChecklistItem).where(
            CandidateChecklistItem.property_id == property_id, CandidateChecklistItem.category == category,
        ))
        if check:
            check.status, check.source, check.evidence = checklist_status, analysis_type, evidence
            check.completed_at = now if checklist_status == "done" else None
            check.updated = now
        item.updated = now
        session.get(PurchaseCase, case_id).updated = now
        return True


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


def _property_dict(item: CaseProperty, history: HistoryRecord | None = None, analyses: list | None = None, checklist: list | None = None) -> dict:
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
        "analyses": analyses or [], "checklist": checklist or [],
        "review_progress": round(sum(c["status"] == "done" for c in (checklist or [])) / len(checklist or []) * 100) if checklist else 0,
        "created": item.created, "updated": item.updated,
    }


def _analysis_dict(item: CandidateAnalysis) -> dict:
    freshness = analysis_freshness(
        item.analysis_type, item.analyzed_at, item.expires_at, item.status,
    )
    return {"id": item.id, "analysis_type": item.analysis_type, "reference_id": item.reference_id,
            "status": freshness["status"], "summary": item.summary or {}, "analyzed_at": item.analyzed_at,
            "expires_at": freshness["expires_at"], "days_remaining": freshness["days_remaining"],
            "updated": item.updated}


def _checklist_dict(item: CandidateChecklistItem) -> dict:
    return {"id": item.id, "category": item.category, "title": item.title, "status": item.status,
            "source": item.source, "evidence": item.evidence, "sort_order": item.sort_order,
            "completed_at": item.completed_at, "updated": item.updated}


def _region_dict(item: CaseRegion) -> dict:
    return {
        "id": item.id, "case_id": item.case_id,
        "region_code": item.region_code, "region_name": item.region_name,
        "source": item.source, "property_type": item.property_type,
        "budget_max_won": item.budget_max_won,
        "period_from": item.period_from, "period_to": item.period_to,
        "stats_snapshot": item.stats_snapshot or {}, "created": item.created,
    }
