import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_PAGES   = ["/login", "/register"];          // 로그인 상태면 접근 불필요
const OPEN_PAGES   = ["/privacy", "/terms"];           // 로그인 여부와 무관하게 공개

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("auth_token");

  if (OPEN_PAGES.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p));

  if (!token && !isAuthPage) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (token && isAuthPage) {
    return NextResponse.redirect(new URL("/appraisal", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
