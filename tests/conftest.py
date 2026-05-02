"""
conftest.py — pytest 공통 설정

backend/와 프로젝트 루트를 sys.path에 추가해
테스트에서 모든 모듈을 직접 import할 수 있게 한다.
"""

import sys
import os

_root    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend = os.path.join(_root, "backend")

for _p in [_backend, _root]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
