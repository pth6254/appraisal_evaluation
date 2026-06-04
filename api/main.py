"""
main.py — FastAPI 진입점

실행: uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 프로젝트 루트 및 backend/ 를 sys.path 선두에 삽입
_API_DIR      = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_API_DIR)
_BACKEND_DIR  = os.path.join(_PROJECT_ROOT, "backend")
for _p in [_PROJECT_ROOT, _BACKEND_DIR, _API_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api.routes import appraisal, address, auth, comparison, history, recommendation, simulation
from api import auth_db as _adb
from api import history_db as _hdb
from backend.cache_db import init_cache_db as _init_cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _hdb.init()
    _adb.init()
    _init_cache()
    logger.info("FastAPI 시작 — history DB, auth DB, cache DB 초기화 완료")
    yield
    logger.info("FastAPI 종료")


app = FastAPI(
    title="부동산 감정평가 AI API",
    description="LangGraph 기반 부동산 가치 분석·추천·시뮬레이션 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for _router in [
    auth.router,
    appraisal.router,
    recommendation.router,
    simulation.router,
    comparison.router,
    history.router,
    address.router,
]:
    app.include_router(_router, prefix="/api")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
