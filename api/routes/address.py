"""GET /api/address/search — Kakao 주소·키워드 검색 프록시"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal

import requests
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["address"])

_KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
_KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"


def _kakao_request(query: str, search_type: str) -> dict:
    api_key = os.getenv("KAKAO_REST_API_KEY", "")
    if not api_key:
        raise ValueError("KAKAO_REST_API_KEY 환경변수 미설정")

    headers = {"Authorization": f"KakaoAK {api_key}"}
    url     = _KAKAO_KEYWORD_URL if search_type == "keyword" else _KAKAO_ADDRESS_URL
    params  = {"query": query, "size": 15}

    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


@router.get("/address/search")
async def search_address(query: str, type: Literal["keyword", "address"] = "keyword"):
    if not query.strip():
        return {"documents": [], "meta": {"total_count": 0}}
    try:
        result = await asyncio.to_thread(_kakao_request, query, type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except requests.RequestException as e:
        logger.warning("Kakao API 오류: %s", e)
        raise HTTPException(status_code=502, detail="Kakao API 호출 실패")
