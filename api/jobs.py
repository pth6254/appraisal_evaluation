"""
jobs.py — 인프로세스 비동기 작업 매니저

감정(시세추정) 파이프라인처럼 수십 초~수 분 걸리는 작업을
HTTP 요청과 분리해 백그라운드 스레드로 실행하고,
job_id로 진행 상태·결과를 조회한다.

흐름:
  POST /appraisal/jobs      → create() → {job_id}
  GET  /appraisal/jobs/{id} → get()    → {status, step, history_id, result?}

주의:
  - 단일 프로세스 메모리 저장이므로 서버 재시작 시 진행 중 작업은 유실된다.
    (결과는 완료 즉시 history DB에 영속화되므로 완료된 작업은 안전)
  - 멀티 워커(uvicorn --workers N) 배포 시에는 Redis 등 외부 저장소로
    교체해야 한다. 현재 docker-compose는 단일 워커.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable, Optional

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()

FINISHED_TTL = 60 * 60       # 완료/실패 작업 보관 1시간
MAX_CONCURRENT = 4           # 동시 실행 상한 (LLM·외부 API 부하 보호)

_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT)


def _cleanup_locked():
    """만료된 완료 작업 제거 (_LOCK 보유 상태에서 호출)."""
    now = time.time()
    expired = [
        jid for jid, j in _JOBS.items()
        if j["status"] in ("done", "error") and now - j["finished_at"] > FINISHED_TTL
    ]
    for jid in expired:
        del _JOBS[jid]


def create(runner: Callable[[Callable[[str], None]], dict],
           on_done: Optional[Callable[[dict], Any]] = None) -> str:
    """
    작업 생성 및 백그라운드 실행.

    Args:
        runner : fn(set_step) -> result dict. set_step(str)으로 진행 단계 보고.
                 result에 "error" 키가 있으면 실패로 처리.
        on_done: 성공 시 result를 받아 부가 처리(이력 저장 등) 후
                 job에 병합할 dict를 반환하는 콜백 (예: {"history_id": 3}).
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
    }
    with _LOCK:
        _cleanup_locked()
        _JOBS[job_id] = job

    def set_step(step: str):
        with _LOCK:
            job["step"] = step

    def _run():
        with _SEMAPHORE:
            with _LOCK:
                job["status"] = "running"
            try:
                result = runner(set_step)
                if isinstance(result, dict) and result.get("error"):
                    with _LOCK:
                        job["status"]      = "error"
                        job["error"]       = str(result["error"])
                        job["result"]      = result
                        job["finished_at"] = time.time()
                    return

                extra = {}
                if on_done is not None:
                    try:
                        extra = on_done(result) or {}
                    except Exception as e:
                        # 부가 처리 실패(이력 저장 등)는 작업 실패로 만들지 않음
                        print(f"[jobs] on_done 오류: {e}")

                with _LOCK:
                    job["status"]      = "done"
                    job["result"]      = result
                    job["extra"]       = extra
                    job["finished_at"] = time.time()
            except Exception as e:
                with _LOCK:
                    job["status"]      = "error"
                    job["error"]       = str(e)
                    job["finished_at"] = time.time()

    threading.Thread(target=_run, daemon=True).start()
    return job_id


def get(job_id: str, include_result: bool = True) -> Optional[dict]:
    """작업 상태 조회. 없으면 None."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
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
