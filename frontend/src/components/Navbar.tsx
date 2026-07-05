"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/",               label: "🏡 홈",            exact: true },
  { href: "/appraisal",      label: "🏠 AI 시세추정" },
  { href: "/report",         label: "📊 결과 리포트" },
  { href: "/dashboard",      label: "📋 이력 대시보드" },
  { href: "/recommendation", label: "✨ 매물 추천" },
  { href: "/simulation",     label: "📈 투자 시뮬레이션" },
  { href: "/comparison",     label: "⚖️ 매물 비교" },
];

export default function Navbar() {
  const path      = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 h-full w-[220px] bg-slate-900 text-white flex flex-col z-50 shadow-lg">
      <div className="px-5 py-5 border-b border-slate-700">
        <div className="text-lg font-bold text-blue-400">부동산 AI</div>
        <div className="text-xs text-slate-400 mt-0.5">시세추정 · 추천 · 시뮬레이션</div>
      </div>
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV.map(({ href, label, exact }) => {
          const active = exact ? path === href : (path === href || path.startsWith(href + "/"));
          return (
            <Link
              key={href} href={href}
              className={`flex items-center px-5 py-2.5 text-sm transition-colors ${
                active
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-4 border-t border-slate-700 space-y-2">
        {user && (
          <>
            <div className="text-xs text-slate-300 truncate">
              {user.name || user.email}
            </div>
            <div className="text-xs text-slate-500 truncate">{user.email}</div>
            <button
              onClick={logout}
              className="w-full text-left text-xs text-slate-400 hover:text-white transition-colors py-1"
            >
              로그아웃
            </button>
          </>
        )}
        <div className="text-xs text-slate-600">⚠️ 샘플 데이터 기반 · 참고용</div>
      </div>
    </aside>
  );
}
