"""
rate_limit.py — 공용 레이트 리미터 (slowapi)

IP 기준 요청 제한. 라우트별 한도는 각 엔드포인트 데코레이터에서 지정한다.
테스트·개발에서 끄려면 DISABLE_RATE_LIMIT=1.
"""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("DISABLE_RATE_LIMIT") != "1",
)
