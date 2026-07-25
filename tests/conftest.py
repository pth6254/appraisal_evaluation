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


def truncate_tables(*models) -> None:
    """
    지정한 SQLAlchemy 모델의 테이블을 비운다.

    PostgreSQL 전환 전에는 SQLite 파일을 tmp_path로 monkeypatch해서 테스트마다
    DB를 통째로 격리했다 (test_access_control.py, test_transaction_store.py,
    test_rights_and_chat.py 가 이 패턴을 썼다). 이제 모든 워커가 같은 Postgres
    인스턴스를 보므로 파일 스와핑 대신 관련 테이블만 비워 격리한다 — 이 프로젝트
    데이터 규모(테스트용 몇 건)에서는 TRUNCATE로 충분하고 스키마 재생성보다 빠르다.
    DATABASE_URL이 필요하므로, DB에 실제로 접근하는 테스트에서만 호출할 것.
    """
    from db.base import init_db, session_scope

    init_db()
    with session_scope() as session:
        for model in models:
            session.query(model).delete()
