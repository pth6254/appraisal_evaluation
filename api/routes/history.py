"""GET/DELETE /api/history — 감정평가 이력"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api import history_db
from api.deps import get_current_user

router = APIRouter(tags=["history"])


@router.get("/history")
def get_history(
    limit: int = 20,
    offset: int = 0,
    keyword: str = "",
    user: dict = Depends(get_current_user),
):
    if keyword:
        rows = history_db.search_by_query(keyword, limit=limit, user_id=user["id"])
    else:
        rows = history_db.load_all(limit=limit, offset=offset, user_id=user["id"])

    total = history_db.count_all(user_id=user["id"])
    return {"total": total, "items": rows}


@router.get("/history/{record_id}")
def get_history_one(record_id: int, user: dict = Depends(get_current_user)):
    row = history_db.load_one(record_id)
    if not row:
        raise HTTPException(status_code=404, detail="이력 없음")
    return row


@router.delete("/history/{record_id}")
def delete_history_one(record_id: int, user: dict = Depends(get_current_user)):
    history_db.delete_one(record_id, user_id=user["id"])
    return {"ok": True}


@router.delete("/history")
def delete_history_all(user: dict = Depends(get_current_user)):
    history_db.delete_all(user_id=user["id"])
    return {"ok": True}
