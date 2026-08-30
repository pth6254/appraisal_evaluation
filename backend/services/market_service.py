"""API와 컨시어지 도구가 함께 사용하는 실거래 시장 집계 서비스."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import case, func, select

from db.base import session_scope
from db.models import LegalRegion, Transaction

PROPERTY_ENDPOINTS = {
    "all": None,
    "apartment": "RTMSDataSvcAptTrade",
    "row_house": "RTMSDataSvcRHTrade",
    "detached": "RTMSDataSvcSHTrade",
    "officetel": "RTMSDataSvcOffiTrade",
    "non_residential": "RTMSDataSvcNrgTrade",
    "industrial": "RTMSDataSvcInduTrade",
    "land": "RTMSDataSvcLandTrade",
}


def list_legal_regions(*, level: str, parent_code: str | None) -> list[dict]:
    with session_scope() as session:
        stmt = (
            select(LegalRegion)
            .where(LegalRegion.is_active.is_(True), LegalRegion.level == level)
            .order_by(LegalRegion.sort_order, LegalRegion.name)
        )
        stmt = stmt.where(
            LegalRegion.parent_code.is_(None)
            if parent_code is None else LegalRegion.parent_code == parent_code
        )
        rows = session.scalars(stmt).all()
        return [
            {
                "code": row.code,
                "parent_code": row.parent_code,
                "name": row.name,
                "full_name": row.full_name,
                "level": row.level,
                "lawd_code": row.lawd_code,
            }
            for row in rows
        ]


def resolve_region_name(name: str) -> dict:
    """LLM이 만든 코드를 신뢰하지 않고 정식 법정동 마스터에서 지역명을 해석한다."""
    normalized = name.strip()
    aliases = {"서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
               "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
               "울산": "울산광역시", "세종": "세종특별자치시", "제주": "제주특별자치도"}
    normalized = aliases.get(normalized, normalized)
    with session_scope() as session:
        exact = session.scalars(
            select(LegalRegion).where(
                LegalRegion.is_active.is_(True),
                (LegalRegion.full_name == normalized) | (LegalRegion.name == normalized),
            ).order_by(LegalRegion.depth, LegalRegion.sort_order)
        ).all()
    if len(exact) == 1:
        row = exact[0]
        return {"status": "resolved", "code": row.code, "full_name": row.full_name, "level": row.level}
    if exact:
        return {"status": "ambiguous", "candidates": [
            {"code": row.code, "full_name": row.full_name, "level": row.level} for row in exact[:10]
        ]}
    return {"status": "not_found", "candidates": []}


def get_region_market_summary(
    *,
    months: int,
    property_type: str,
    budget_max_won: int | None = None,
    region_code: str | None = None,
    legacy_sido_name: str | None = None,
) -> dict:
    if property_type not in PROPERTY_ENDPOINTS:
        raise ValueError(f"지원하지 않는 부동산 유형: {property_type}")
    endpoint = PROPERTY_ENDPOINTS[property_type]
    budget_max = budget_max_won // 10_000 if budget_max_won else 0

    with session_scope() as session:
        selected_region = session.get(LegalRegion, region_code) if region_code else None
        if region_code and (not selected_region or not selected_region.is_active):
            raise HTTPException(status_code=404, detail="선택한 행정구역을 찾을 수 없습니다")
        max_ym = session.scalar(select(func.max(Transaction.deal_ym)))
        if not max_ym:
            return {"source": "국토교통부 실거래가", "period": None, "items": []}
        year, month = int(max_ym[:4]), int(max_ym[4:])
        absolute = year * 12 + month - months
        min_ym = f"{absolute // 12:04d}{absolute % 12 + 1:02d}"

        budget_fit = func.sum(case((Transaction.price <= budget_max, 1), else_=0)) if budget_max else func.count()
        stmt = (
            select(
                LegalRegion.full_name.label("region_name"), LegalRegion.code.label("region_code"),
                LegalRegion.lawd_code, func.count(Transaction.id).label("deal_count"),
                func.round(func.avg(Transaction.price)).label("avg_price"),
                func.percentile_cont(0.5).within_group(Transaction.price).label("median_price"),
                func.percentile_cont(0.25).within_group(Transaction.price).label("price_q1"),
                func.percentile_cont(0.75).within_group(Transaction.price).label("price_q3"),
                func.round(func.avg(Transaction.per_sqm)).label("avg_per_sqm"),
                func.percentile_cont(0.5).within_group(Transaction.per_sqm).label("median_per_sqm"),
                func.count(func.distinct(Transaction.apt_name)).label("asset_count"),
                func.max(Transaction.deal_ym).label("last_deal_ym"), budget_fit.label("budget_fit_count"),
            )
            .join(Transaction, Transaction.lawd_cd == LegalRegion.lawd_code)
            .where(
                LegalRegion.is_active.is_(True), LegalRegion.level == "sigungu",
                Transaction.deal_ym >= min_ym, Transaction.deal_ym <= max_ym,
                Transaction.is_cancelled.is_(False),
            )
            .group_by(LegalRegion.full_name, LegalRegion.code, LegalRegion.lawd_code)
            .order_by(func.avg(Transaction.per_sqm), LegalRegion.full_name)
        )
        if selected_region:
            if selected_region.level == "sido":
                stmt = stmt.where(LegalRegion.sido_code == selected_region.sido_code)
            elif selected_region.level == "sigungu":
                stmt = stmt.where(LegalRegion.full_name.like(f"{selected_region.full_name}%"))
            else:
                raise HTTPException(status_code=422, detail="시장 비교는 시·도 또는 시·군·구 단위만 지원합니다")
        elif legacy_sido_name:
            stmt = stmt.where(LegalRegion.full_name.like(f"{legacy_sido_name} %"))
        if endpoint:
            stmt = stmt.where(Transaction.endpoint == endpoint)
        rows = session.execute(stmt).mappings().all()

    return {
        "source": "국토교통부 실거래가", "price_unit": "만원",
        "period": {"from": min_ym, "to": max_ym}, "property_type": property_type,
        "scope": ({"code": selected_region.code, "name": selected_region.name,
                   "full_name": selected_region.full_name, "level": selected_region.level}
                  if selected_region else None),
        "items": [_market_item(row) for row in rows],
    }


def _market_item(row) -> dict:
    sample_size = int(row["deal_count"] or 0)
    budget_fit_count = int(row["budget_fit_count"] or 0)
    return {
        "region_name": row["region_name"], "region_code": row["region_code"],
        "lawd_code": row["lawd_code"], "deal_count": sample_size,
        "sample_size": sample_size,
        "avg_price": int(row["avg_price"] or 0),
        "median_price": int(row["median_price"] or 0),
        "price_q1": int(row["price_q1"] or 0),
        "price_q3": int(row["price_q3"] or 0),
        "avg_per_sqm": int(row["avg_per_sqm"] or 0),
        "median_per_sqm": int(row["median_per_sqm"] or 0),
        "asset_count": row["asset_count"], "last_deal_ym": row["last_deal_ym"],
        "budget_fit_count": budget_fit_count,
        "budget_fit_ratio": round(budget_fit_count / sample_size, 4) if sample_size else 0.0,
        # 지역 간 동일한 결정 규칙을 적용해 LLM이 신뢰도를 자의적으로 만들지 못하게 한다.
        "confidence": "high" if sample_size >= 100 else "medium" if sample_size >= 30 else "low",
    }
