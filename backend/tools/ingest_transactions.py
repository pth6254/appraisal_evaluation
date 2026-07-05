"""
ingest_transactions.py — 국토부 실거래가 배치 수집 CLI

MOLIT API에서 지역 × 유형 × 월 단위로 실거래 데이터를 수집해
로컬 스토어(data/transactions.db)에 적재한다.
적재된 키는 price_engine이 API 호출 없이 로컬에서 조회한다.

사용 예:
  # 서초구·강남구 주거용 최근 12개월
  python backend/tools/ingest_transactions.py --regions 서초구,강남구 --months 12

  # 등록된 전체 지역, 주거용+상업용 6개월
  python backend/tools/ingest_transactions.py --all --categories 주거용,상업용

  # 이미 신선한 키도 강제 재수집
  python backend/tools/ingest_transactions.py --regions 서초구 --force

주의:
  - 공공데이터포털 개발계정 키는 일일 트래픽 제한(보통 1,000건)이 있다.
    총 호출 수 = 지역 × 엔드포인트 × 월. 실행 전 출력되는 예상치를 확인할 것.
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_TOOLS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR  = os.path.dirname(_TOOLS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in [_BACKEND_DIR, _PROJECT_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import transaction_store
from cache_db import get_lawd_code, list_region_codes
from price_engine import (
    MOLIT_API_KEY,
    MOLIT_BASE_URL,
    MOLIT_ENDPOINTS,
    _endpoint_name,
    _fetch_one_month_api,
    _get_recent_deal_ymds,
)

VALID_CATEGORIES = ["주거용", "상업용", "업무용", "산업용", "토지"]


def _endpoints_for(categories: list[str]) -> list[tuple[str, str]]:
    """카테고리 목록 → 중복 제거된 (category, endpoint_url) 목록."""
    seen: set[tuple[str, str]] = set()
    result = []
    for (cat, _detail), path in MOLIT_ENDPOINTS.items():
        if cat not in categories:
            continue
        url = MOLIT_BASE_URL + path
        if (cat, url) not in seen:
            seen.add((cat, url))
            result.append((cat, url))
    return result


def _ingest_one(job: tuple, safe_key: str, force: bool) -> str:
    """단일 (지역, 엔드포인트, 월) 수집. 반환: 'fetched' | 'skipped' | 'failed'"""
    region_name, lawd_cd, category, url, ym = job
    endpoint = _endpoint_name(url)

    if not force:
        cached = transaction_store.get_month(endpoint, category, lawd_cd, ym)
        if cached is not None:
            return "skipped"

    parsed = _fetch_one_month_api(url, safe_key, lawd_cd, ym, category)
    if parsed is None:
        return "failed"

    transaction_store.put_month(endpoint, category, lawd_cd, ym, parsed)
    return "fetched"


def main():
    parser = argparse.ArgumentParser(description="국토부 실거래가 배치 수집")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--regions", help="쉼표 구분 지역명 (예: 서초구,강남구)")
    group.add_argument("--all", action="store_true", help="등록된 전체 지역 수집")
    parser.add_argument("--months", type=int, default=6, help="수집 개월 수 (기본 6)")
    parser.add_argument("--categories", default="주거용",
                        help=f"쉼표 구분 유형 (기본 주거용, 가능: {','.join(VALID_CATEGORIES)})")
    parser.add_argument("--force", action="store_true", help="신선한 키도 강제 재수집")
    parser.add_argument("--workers", type=int, default=4, help="동시 요청 수 (기본 4)")
    parser.add_argument("--yes", "-y", action="store_true", help="확인 없이 바로 실행")
    args = parser.parse_args()

    if not MOLIT_API_KEY:
        sys.exit("❌ MOLIT_API_KEY 미설정 — .env 파일을 확인하세요")

    # ── 지역 결정 ──
    if args.all:
        regions = [(r["region_name"], r["lawd_code"]) for r in list_region_codes()]
    else:
        regions = []
        for name in args.regions.split(","):
            name = name.strip()
            if not name:
                continue
            code = get_lawd_code(name)
            if code:
                regions.append((name, code))
            else:
                print(f"⚠️  '{name}' 지역코드 없음 — 건너뜀")
    if not regions:
        sys.exit("❌ 수집할 지역이 없습니다")

    # ── 유형 결정 ──
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    invalid = [c for c in categories if c not in VALID_CATEGORIES]
    if invalid:
        sys.exit(f"❌ 잘못된 유형: {invalid} (가능: {VALID_CATEGORIES})")

    endpoints = _endpoints_for(categories)
    ymds      = _get_recent_deal_ymds(months=args.months)

    # ── 작업 목록 ──
    jobs = [
        (region_name, lawd_cd, cat, url, ym)
        for region_name, lawd_cd in regions
        for cat, url in endpoints
        for ym in ymds
    ]

    print(f"수집 계획: 지역 {len(regions)}개 × 엔드포인트 {len(endpoints)}개 × {args.months}개월"
          f" = 최대 {len(jobs)}회 API 호출")
    print(f"  지역: {', '.join(n for n, _ in regions[:10])}{' 외' if len(regions) > 10 else ''}")
    print(f"  기간: {ymds[0]} ~ {ymds[-1]}")
    if not args.yes:
        answer = input("계속할까요? [y/N] ").strip().lower()
        if answer != "y":
            sys.exit("중단")

    safe_key = MOLIT_API_KEY.replace("+", "%2B").replace("=", "%3D")
    counts   = {"fetched": 0, "skipped": 0, "failed": 0}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_ingest_one, job, safe_key, args.force): job for job in jobs}
        done = 0
        for future in as_completed(futures):
            outcome = future.result()
            counts[outcome] += 1
            done += 1
            if done % 20 == 0 or done == len(jobs):
                print(f"  진행 {done}/{len(jobs)} — 수집 {counts['fetched']}"
                      f" / 스킵 {counts['skipped']} / 실패 {counts['failed']}")

    print("\n완료:")
    print(f"  API 수집  : {counts['fetched']}건")
    print(f"  스킵(신선): {counts['skipped']}건")
    print(f"  실패      : {counts['failed']}건")

    print("\n스토어 현황:")
    for k, v in transaction_store.store_stats().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
