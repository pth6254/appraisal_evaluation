"""매수 실행 계획 저장소. 모든 공개 함수는 케이스 소유자를 먼저 제한한다."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select

from backend.services.analysis_freshness import analysis_freshness
from backend.services.execution_plan_service import TASK_TEMPLATES, due_date_for, readiness_summary
from db.base import session_scope
from db.models import CandidateAnalysis, CaseExecutionPlan, CaseExecutionTask, PurchaseCase
from db.models import _now_str


def _owned_case(session, case_id: int, user_id: int) -> PurchaseCase | None:
    return session.scalar(select(PurchaseCase).where(
        PurchaseCase.id == case_id, PurchaseCase.user_id == user_id,
    ))


def _seed_tasks(session, plan: CaseExecutionPlan) -> None:
    existing = set(session.scalars(select(CaseExecutionTask.template_key).where(
        CaseExecutionTask.plan_id == plan.id, CaseExecutionTask.template_key.is_not(None),
    )))
    for order, (key, phase, title, actor, anchor, offset, required) in enumerate(TASK_TEMPLATES):
        if key in existing:
            continue
        session.add(CaseExecutionTask(
            plan_id=plan.id, case_id=plan.case_id, property_id=plan.property_id,
            template_key=key, phase=phase, title=title, actor_type=actor,
            required=required, source="system", sort_order=order,
            due_date=due_date_for(anchor, offset, plan.contract_planned_date, plan.closing_planned_date),
        ))


def ensure_execution_plan(case_id: int, property_id: int, user_id: int) -> dict | None:
    with session_scope() as session:
        case = _owned_case(session, case_id, user_id)
        if not case or case.selected_property_id != property_id:
            return None
        plan = session.scalar(select(CaseExecutionPlan).where(CaseExecutionPlan.case_id == case.id))
        if not plan:
            plan = CaseExecutionPlan(case_id=case.id, property_id=property_id)
            session.add(plan)
            session.flush()
        elif plan.property_id != property_id:
            plan.property_id = property_id
            plan.updated = _now_str()
            session.execute(delete(CaseExecutionTask).where(
                CaseExecutionTask.plan_id == plan.id,
                CaseExecutionTask.source == "system",
            ))
            for task in session.scalars(select(CaseExecutionTask).where(
                CaseExecutionTask.plan_id == plan.id, CaseExecutionTask.source == "user",
            )):
                task.property_id = property_id
                task.updated = _now_str()
            session.flush()
        _seed_tasks(session, plan)
        session.flush()
        return _execution_dict(session, plan)


def get_execution(case_id: int, user_id: int) -> dict | None:
    with session_scope() as session:
        case = _owned_case(session, case_id, user_id)
        if not case:
            return None
        if not case.selected_property_id:
            return {"case_id": case.id, "requires_selection": True, "plan": None, "tasks": [], "summary": readiness_summary([])}
        plan = session.scalar(select(CaseExecutionPlan).where(CaseExecutionPlan.case_id == case.id))
        if not plan:
            plan = CaseExecutionPlan(case_id=case.id, property_id=case.selected_property_id)
            session.add(plan)
            session.flush()
        _seed_tasks(session, plan)
        session.flush()
        _sync_analysis_evidence(session, plan)
        session.flush()
        return _execution_dict(session, plan)


def update_plan(case_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = _owned_case(session, case_id, user_id)
        if not case or not case.selected_property_id:
            return None
        plan = session.scalar(select(CaseExecutionPlan).where(CaseExecutionPlan.case_id == case.id))
        if not plan:
            plan = CaseExecutionPlan(case_id=case.id, property_id=case.selected_property_id)
            session.add(plan)
            session.flush()
            _seed_tasks(session, plan)
        contract_date = data.get("contract_planned_date", plan.contract_planned_date)
        closing_date = data.get("closing_planned_date", plan.closing_planned_date)
        if contract_date and closing_date and contract_date > closing_date:
            raise ValueError("invalid_date_order")
        for key, value in data.items():
            setattr(plan, key, value)
        plan.updated = case.updated = _now_str()
        by_key = {task.template_key: task for task in session.scalars(select(CaseExecutionTask).where(
            CaseExecutionTask.plan_id == plan.id, CaseExecutionTask.template_key.is_not(None),
        ))}
        for key, _phase, _title, _actor, anchor, offset, _required in TASK_TEMPLATES:
            task = by_key.get(key)
            if task and task.status not in {"done", "not_applicable"}:
                task.due_date = due_date_for(anchor, offset, contract_date, closing_date)
                task.updated = _now_str()
        session.flush()
        return _execution_dict(session, plan)


def add_task(case_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = _owned_case(session, case_id, user_id)
        if not case:
            return None
        plan = session.scalar(select(CaseExecutionPlan).where(CaseExecutionPlan.case_id == case.id))
        if not plan:
            return None
        sort_order = session.scalar(select(func.max(CaseExecutionTask.sort_order)).where(CaseExecutionTask.plan_id == plan.id)) or 0
        task = CaseExecutionTask(plan_id=plan.id, case_id=case.id, property_id=plan.property_id,
                                 source="user", sort_order=sort_order + 1, **data)
        session.add(task)
        plan.updated = case.updated = _now_str()
        session.flush()
        return _task_dict(task)


def update_task(case_id: int, task_id: int, user_id: int, data: dict) -> dict | None:
    with session_scope() as session:
        case = _owned_case(session, case_id, user_id)
        if not case:
            return None
        task = session.scalar(select(CaseExecutionTask).where(
            CaseExecutionTask.id == task_id, CaseExecutionTask.case_id == case.id,
        ))
        if not task:
            return None
        resulting_status = data.get("status", task.status)
        checked_by = data.get("checked_by", task.checked_by)
        outcome = data.get("outcome", task.outcome)
        if resulting_status in {"done", "problem"} and (not checked_by.strip() or not outcome.strip()):
            raise ValueError("verification_required")
        for key, value in data.items():
            setattr(task, key, value)
        task.completed_at = _now_str() if resulting_status in {"done", "problem", "not_applicable"} else None
        task.updated = case.updated = _now_str()
        session.flush()
        return _task_dict(task)


def delete_task(case_id: int, task_id: int, user_id: int) -> bool | None:
    with session_scope() as session:
        case = _owned_case(session, case_id, user_id)
        if not case:
            return None
        task = session.scalar(select(CaseExecutionTask).where(
            CaseExecutionTask.id == task_id, CaseExecutionTask.case_id == case.id,
        ))
        if not task:
            return False
        if task.source != "user":
            raise ValueError("system_task")
        session.delete(task)
        case.updated = _now_str()
        return True


def _sync_analysis_evidence(session, plan: CaseExecutionPlan) -> None:
    analyses = {item.analysis_type: item for item in session.scalars(select(CandidateAnalysis).where(
        CandidateAnalysis.property_id == plan.property_id,
    ))}
    tasks = {item.template_key: item for item in session.scalars(select(CaseExecutionTask).where(
        CaseExecutionTask.plan_id == plan.id, CaseExecutionTask.template_key.in_(["appraisal_review", "rights_check", "funding_check"]),
    ))}
    now = _now_str()
    appraisal = analyses.get("appraisal")
    if appraisal and tasks.get("appraisal_review"):
        fresh = analysis_freshness("appraisal", appraisal.analyzed_at, appraisal.expires_at, appraisal.status)
        task = tasks["appraisal_review"]
        # 자동 연결한 결과만 갱신한다. 사용자가 직접 확인한 기록은 분석 재실행으로 덮지 않는다.
        if fresh["status"] == "completed" and task.checked_by in {"", "시스템"}:
            task.status, task.checked_by = "done", "시스템"
            task.outcome, task.completed_at = "유효한 시세분석 결과가 연결됨", now
        elif fresh["status"] == "stale" and task.checked_by == "시스템":
            task.status, task.checked_by, task.completed_at = "scheduled", "", None
            task.outcome = "시세분석 유효기간 만료 — 갱신 필요"
    rights = analyses.get("rights")
    if rights and tasks.get("rights_check"):
        fresh = analysis_freshness("rights", rights.analyzed_at, rights.expires_at, rights.status)
        task = tasks["rights_check"]
        grade = (rights.summary or {}).get("risk_grade")
        if fresh["status"] == "completed" and task.checked_by in {"", "시스템"}:
            task.checked_by, task.completed_at = "시스템", now
            task.status = "done" if grade == "safe" else "problem"
            task.outcome = f"문서 기반 권리분석 결과: {(rights.summary or {}).get('risk_label') or grade}"
        elif fresh["status"] == "stale" and task.checked_by == "시스템":
            task.status, task.checked_by, task.completed_at = "scheduled", "", None
            task.outcome = "권리분석 유효기간 만료 — 최신 문서 재확인 필요"
    funding = analyses.get("simulation")
    if tasks.get("funding_check"):
        task = tasks["funding_check"]
        if funding:
            fresh = analysis_freshness("simulation", funding.analyzed_at, funding.expires_at, funding.status)
            # 사용자가 남긴 은행 상담 근거를 단순 시뮬레이션 안내로 덮어쓰지 않는다.
            if not task.evidence_note or task.evidence_note.startswith("자금 시뮬레이션"):
                task.evidence_note = "자금 시뮬레이션 결과 연결됨 — 은행 승인과는 다름" if fresh["status"] == "completed" else "자금 시뮬레이션 갱신 필요"


def _execution_dict(session, plan: CaseExecutionPlan) -> dict:
    tasks = [_task_dict(task) for task in session.scalars(select(CaseExecutionTask).where(
        CaseExecutionTask.plan_id == plan.id,
    ).order_by(CaseExecutionTask.sort_order, CaseExecutionTask.id))]
    return {
        "case_id": plan.case_id, "requires_selection": False,
        "plan": {"id": plan.id, "property_id": plan.property_id,
                 "contract_planned_date": plan.contract_planned_date,
                 "closing_planned_date": plan.closing_planned_date,
                 "status": plan.status, "created": plan.created, "updated": plan.updated},
        "tasks": tasks, "summary": readiness_summary(tasks),
    }


def _task_dict(task: CaseExecutionTask) -> dict:
    overdue = bool(task.due_date and date.fromisoformat(task.due_date) < date.today() and task.status not in {"done", "not_applicable"})
    return {"id": task.id, "plan_id": task.plan_id, "phase": task.phase,
            "template_key": task.template_key, "title": task.title, "description": task.description,
            "actor_type": task.actor_type, "status": task.status, "required": task.required,
            "due_date": task.due_date, "overdue": overdue, "completed_at": task.completed_at,
            "checked_by": task.checked_by, "outcome": task.outcome,
            "evidence_note": task.evidence_note, "follow_up": task.follow_up,
            "source": task.source, "sort_order": task.sort_order,
            "created": task.created, "updated": task.updated}
