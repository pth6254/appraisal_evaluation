"""
rate_limit.py — 공용 레이트 리미터 (slowapi + Redis)

IP 기준 요청 제한. 라우트별 한도는 각 엔드포인트 데코레이터에서 지정한다.
테스트·개발에서 끄려면 DISABLE_RATE_LIMIT=1.

이전에는 slowapi 기본값인 프로세스 메모리 저장소를 썼다 — uvicorn을
--workers N 으로 띄우면 워커마다 카운터가 따로 놀아, 실질 한도가 워커
수만큼 늘어나는 문제가 있었다 (로그인 브루트포스 방어에서 특히 치명적).
REDIS_URL을 storage_uri로 넘겨 워커 간 카운터를 공유한다.
"""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_ENABLED = os.getenv("DISABLE_RATE_LIMIT") != "1"

if _ENABLED:
    _REDIS_URL = os.getenv("REDIS_URL", "")
    if not _REDIS_URL:
        raise RuntimeError(
            "REDIS_URL 환경변수가 설정되지 않았습니다 (레이트 리밋이 워커 간 상태를 "
            "공유하려면 필요). 개발 중 끄려면 DISABLE_RATE_LIMIT=1."
        )
    _STORAGE_URI = _REDIS_URL
else:
    _STORAGE_URI = "memory://"   # 비활성화 상태에서는 카운터 자체를 쓰지 않으므로 무관

limiter = Limiter(
    key_func=get_remote_address,
    enabled=_ENABLED,
    storage_uri=_STORAGE_URI,
)
