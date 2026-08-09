"""
email_service.py — 트랜잭션 메일 발송 (비밀번호 재설정 등)

Sentry 연동과 동일한 opt-in 패턴이다: RESEND_API_KEY 가 없으면 실제 발송 대신
서버 로그에 내용을 출력한다. 덕분에

  - 로컬 개발·CI 가 외부 메일 서비스에 의존하지 않고,
  - 도메인 인증(SPF/DKIM) 준비가 끝나기 전에도 재설정 흐름 전체를 검증할 수 있으며,
  - 초대 베타 단계에서는 운영자가 로그의 링크를 수동 전달해 계정을 복구해줄 수 있다.

키를 .env 에 넣는 순간 코드 변경 없이 실발송으로 전환된다.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
MAIL_FROM      = os.getenv("MAIL_FROM", "no-reply@localhost")
MAIL_TIMEOUT_S = 10.0


def _send(to: str, subject: str, html: str, text: str) -> bool:
    """
    메일 1건 발송. 성공 여부를 반환하되, 실패해도 예외를 던지지 않는다 —
    호출부(비밀번호 재설정)는 메일 발송 실패를 사용자에게 노출하면 안 되기
    때문이다(계정 존재 여부가 응답 차이로 새어나간다).
    """
    if not RESEND_API_KEY:
        # 개발·CI 폴백: 실제로 보내지 않고 로그로 남긴다.
        logger.warning(
            "[email] RESEND_API_KEY 미설정 — 발송하지 않고 로그로 대체합니다.\n"
            "  To      : %s\n"
            "  Subject : %s\n"
            "  Body    :\n%s",
            to, subject, text,
        )
        return True

    try:
        res = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": MAIL_FROM, "to": [to], "subject": subject, "html": html},
            timeout=MAIL_TIMEOUT_S,
        )
        res.raise_for_status()
        logger.info("[email] 발송 완료 — to=%s subject=%s", to, subject)
        return True
    except Exception:
        # 스택트레이스는 남기되 호출부로는 전파하지 않는다.
        logger.exception("[email] 발송 실패 — to=%s subject=%s", to, subject)
        return False


def send_password_reset(to: str, reset_link: str, ttl_minutes: int) -> bool:
    """비밀번호 재설정 링크 발송."""
    subject = "[부동산 컨시어지] 비밀번호 재설정 안내"
    text = (
        f"비밀번호를 재설정하려면 아래 링크를 열어주세요 ({ttl_minutes}분간 유효).\n\n"
        f"{reset_link}\n\n"
        "본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다. "
        "링크를 사용하기 전까지 비밀번호는 변경되지 않습니다."
    )
    html = f"""\
<div style="font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif;line-height:1.6;color:#1d2823">
  <h2 style="margin:0 0 12px;font-size:18px">비밀번호 재설정</h2>
  <p style="margin:0 0 16px">아래 버튼을 눌러 새 비밀번호를 설정하세요. 링크는 <b>{ttl_minutes}분간</b> 유효합니다.</p>
  <p style="margin:0 0 20px">
    <a href="{reset_link}"
       style="display:inline-block;padding:10px 18px;background:#1e6f4f;color:#fff;
              border-radius:8px;text-decoration:none;font-weight:600">비밀번호 재설정하기</a>
  </p>
  <p style="margin:0 0 8px;font-size:13px;color:#5f6e64">버튼이 동작하지 않으면 아래 주소를 복사해 열어주세요.</p>
  <p style="margin:0 0 20px;font-size:13px;word-break:break-all;color:#5f6e64">{reset_link}</p>
  <hr style="border:0;border-top:1px solid #e2e7e1;margin:20px 0">
  <p style="margin:0;font-size:13px;color:#8a978d">
    본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다. 링크를 사용하기 전까지 비밀번호는 변경되지 않습니다.
  </p>
</div>"""
    return _send(to, subject, html, text)
