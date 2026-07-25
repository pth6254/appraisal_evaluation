"""
jobs.py — 비동기 작업 매니저 (Redis 상태 저장 + 인프로세스 실행)

감정(시세추정) 파이프라인처럼 수십 초~수 분 걸리는 작업을
HTTP 요청과 분리해 백그라운드 스레드로 실행하고,
job_id로 진행 상태·결과를 조회한다.

흐름:
  POST /appraisal/jobs      → create() → {job_id}
  GET  /appraisal/jobs/{id} → get()    → {status, step, history_id, result?}

이전에는 상태를 프로세스 메모리 dict에 저장했다 — uvicorn을 --workers N 으로
띄우면 워커 A가 만든 job을 워커 B가 폴링했을 때 찾지 못하는 문제가 있었다.
이제 상태는 Redis에 저장해 워커가 몇 개든 공유한다.

실제 작업 실행(runner)은 여전히 그 job을 만든 워커의 스레드에서 돈다 —
바뀐 건 상태를 어디서 보느냐지, 어디서 실행하느냐가 아니다. MAX_CONCURRENT
세마포어도 여전히 워커 프로세스마다 로컬이라, 워커 수만큼 전체 동시실행
한도가 자연스럽게 늘어난다 (LLM·외부 API 부하는 워커당 4개로 계속 보호됨).
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any, Callable, Optional

from db.redis_client import get_redis

FINISHED_TTL = 60 * 60       # 완료/실패 작업 Redis 보관 1시간
PENDING_TTL  = 60 * 60 * 2   # queued/running 상태 안전망 TTL — 워커가 죽어도 영구 고아 키로 남지 않게
MAX_CONCURRENT = 4           # 동시 실행 상한 (워커 프로세스당, LLM·외부 API 부하 보호)

_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT)


def _key(job_id: str) -> str:
    return f"job:{job_id}"


def _save(job_id: str, job: dict, ttl: int) -> None:
    get_redis().set(_key(job_id), json.dumps(job, ensure_ascii=False), ex=ttl)


def _load(job_id: str) -> Optional[dict]:
    raw = get_redis().get(_key(job_id))
    return json.loads(raw) if raw is not None else None


def create(runner: Callable[[Callable[[str], None]], dict],
           on_done: Optional[Callable[[dict], Any]] = None,
           owner_id: Optional[int] = None) -> str:
    """
    작업 생성 및 백그라운드 실행.

    Args:
        runner  : fn(set_step) -> result dict. set_step(str)으로 진행 단계 보고.
                  result에 "error" 키가 있으면 실패로 처리.
        on_done : 성공 시 result를 받아 부가 처리(이력 저장 등) 후
                  job에 병합할 dict를 반환하는 콜백 (예: {"history_id": 3}).
        owner_id: 작업을 생성한 사용자 id. 지정하면 get()에서 소유자만 조회 가능.
                  None(비로그인)이면 추측 불가한 job_id 자체가 접근 토큰이 된다.
    Returns:
        job_id
    """
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id":          job_id,
        "status":      "queued",     # queued | running | done | error
        "step":        "",
        "created_at":  time.time(),
        "finished_at": 0.0,
        "result":      None,
        "error":       "",
        "extra":       {},
        "owner_id":    owner_id,
    }
    _save(job_id, job, ttl=PENDING_TTL)

    def set_step(step: str):
        current = _load(job_id) or job
        current["step"] = step
        _save(job_id, current, ttl=PENDING_TTL)

    def _run():
        with _SEMAPHORE:
            current = _load(job_id) or job
            current["status"] = "running"
            _save(job_id, current, ttl=PENDING_TTL)
            try:
                result = runner(set_step)
                current = _load(job_id) or job
                if isinstance(result, dict) and result.get("error"):
                    current["status"]      = "error"
                    current["error"]       = str(result["error"])
                    current["result"]      = result
                    current["finished_at"] = time.time()
                    _save(job_id, current, ttl=FINISHED_TTL)
                    return

                extra = {}
                if on_done is not None:
                    try:
                        extra = on_done(result) or {}
                    except Exception as e:
                        # 부가 처리 실패(이력 저장 등)는 작업 실패로 만들지 않음
                        print(f"[jobs] on_done 오류: {e}")

                current["status"]      = "done"
                current["result"]      = result
                current["extra"]       = extra
                current["finished_at"] = time.time()
                _save(job_id, current, ttl=FINISHED_TTL)
            except Exception as e:
                current = _load(job_id) or job
                current["status"]      = "error"
                current["error"]       = str(e)
                current["finished_at"] = time.time()
                _save(job_id, current, ttl=FINISHED_TTL)

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def get(job_id: str, include_result: bool = True,
        requester_id: Optional[int] = None) -> Optional[dict]:
    """
    작업 상태 조회. 없거나 접근 권한이 없으면 None.

    소유자가 지정된 작업(owner_id is not None)은 동일 사용자만 조회할 수 있다.
    권한 없음도 None으로 반환해 job 존재 여부를 노출하지 않는다.
    """
    job = _load(job_id)
    if job is None:
        return None
    if job.get("owner_id") is not None and job["owner_id"] != requester_id:
        return None
    out = {
        "job_id": job["id"],
        "status": job["status"],
        "step":   job["step"],
        "error":  job["error"],
        **job["extra"],
    }
    if include_result and job["status"] in ("done", "error"):
        out["result"] = job["result"]
    return out
