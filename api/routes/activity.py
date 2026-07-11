"""GET /api/activity — 시세추정·권리점검·상담을 합친 최근 활동 피드"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api import activity_db, history_db
from api.deps import get_current_user

router = APIRouter(tags=["activity"])


@router.get("/activity")
def get_activity(limit: int = 8, user: dict = Depends(get_current_user)):
    items: list[dict] = []

    # 시세추정 이력 (history 테이블)
    for r in history_db.load_all(limit=limit, user_id=user["id"]):
        items.append({
            "type":              "appraisal",
            "id":                r["id"],
            "title":             r["query"],
            "subtitle":          r.get("category") or "",
            "created":           r["created"],
            "estimated_value":   r.get("estimated_value"),
            "valuation_verdict": r.get("valuation_verdict"),
            "investment_grade":  r.get("investment_grade"),
        })

    # 권리점검·상담 활동 (activity 테이블)
    for r in activity_db.load_recent(limit=limit, user_id=user["id"]):
        items.append({
            "type":     r["type"],
            "id":       r["id"],
            "title":    r["title"],
            "subtitle": r["summary"],
            "created":  r["created"],
            **r["meta"],
        })

    items.sort(key=lambda x: x.get("created") or "", reverse=True)
    return {"items": items[:limit]}
