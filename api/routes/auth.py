"""
auth.py — 인증 라우터

POST /api/auth/register        : 이메일/비밀번호 회원가입
POST /api/auth/login           : 이메일/비밀번호 로그인
GET  /api/auth/google          : Google OAuth 시작
GET  /api/auth/google/callback : Google OAuth 콜백
GET  /api/auth/me              : 현재 사용자 정보
POST /api/auth/logout          : 로그아웃
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api import auth_db, auth_utils
from api.deps import get_current_user

router = APIRouter(tags=["auth"])

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/api/auth/google/callback")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:3000")

_COOKIE      = "auth_token"
_COOKIE_AGE  = 7 * 24 * 3600


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE, value=token,
        httponly=True, secure=False, samesite="lax",
        max_age=_COOKIE_AGE, path="/",
    )


# ── 이메일/비밀번호 ──────────────────────────────────────

class RegisterBody(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/auth/register", status_code=201)
def register(body: RegisterBody, response: Response):
    if auth_db.get_by_email(body.email):
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="비밀번호는 8자 이상이어야 합니다")
    hashed = auth_utils.hash_password(body.password)
    user   = auth_db.create_local_user(body.email, hashed, body.name)
    _set_cookie(response, auth_utils.create_jwt(user["id"]))
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


@router.post("/auth/login")
def login(body: LoginBody, response: Response):
    user = auth_db.get_by_email(body.email)
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
    if not auth_utils.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
    _set_cookie(response, auth_utils.create_jwt(user["id"]))
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


# ── Google OAuth ─────────────────────────────────────────

@router.get("/auth/google")
def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth가 설정되지 않았습니다")
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
    }
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@router.get("/auth/google/callback")
async def google_callback(code: str, response: Response):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth가 설정되지 않았습니다")
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]

        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_res.raise_for_status()
        info = user_res.json()

    user = auth_db.get_or_create_oauth_user(
        email=info["email"], name=info.get("name", ""),
        avatar_url=info.get("picture", ""), provider="google", provider_id=info["id"],
    )
    redirect = RedirectResponse(url=FRONTEND_URL, status_code=302)
    _set_cookie(redirect, auth_utils.create_jwt(user["id"]))
    return redirect


# ── 공통 ─────────────────────────────────────────────────

@router.get("/auth/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "id":         user["id"],
        "email":      user["email"],
        "name":       user["name"],
        "avatar_url": user.get("avatar_url", ""),
        "provider":   user.get("provider", "local"),
    }


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(key=_COOKIE, path="/")
    return {"ok": True}
