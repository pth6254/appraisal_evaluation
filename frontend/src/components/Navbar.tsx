"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  Home, Tag, MapPin, TrendingUp, Columns2, ShieldCheck,
  MessageSquareText, FileText, History, Menu, X,
  type LucideIcon,
} from "lucide-react";

type NavItem = { href: string; label: string; icon: LucideIcon; exact?: boolean };
type NavGroup = { label: string | null; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    label: null,
    items: [{ href: "/", label: "홈", icon: Home, exact: true }],
  },
  {
    label: "분석",
    items: [
      { href: "/appraisal",      label: "AI 시세추정",     icon: Tag },
      { href: "/recommendation", label: "매물 추천",       icon: MapPin },
      { href: "/simulation",     label: "투자 시뮬레이션", icon: TrendingUp },
      { href: "/comparison",     label: "매물 비교",       icon: Columns2 },
    ],
  },
  {
    label: "안전·상담",
    items: [
      { href: "/rights", label: "권리관계 점검", icon: ShieldCheck },
      { href: "/chat",   label: "법률·세금 AI",  icon: MessageSquareText },
    ],
  },
  {
    label: "내 기록",
    items: [
      { href: "/report",    label: "결과 리포트",     icon: FileText },
      { href: "/dashboard", label: "이력 대시보드",   icon: History },
    ],
  },
];

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-white">
        <Home size={17} />
      </span>
      <span className="text-[17px] font-extrabold tracking-tight text-white">
        부동산 <em className="not-italic text-accent">컨시어지</em>
      </span>
    </div>
  );
}

function NavList({ path, onNavigate }: { path: string; onNavigate?: () => void }) {
  return (
    <nav className="flex-1 overflow-y-auto px-2.5 py-3">
      {GROUPS.map((group, gi) => (
        <div key={gi} className="mb-4">
          {group.label && (
            <div className="mb-1.5 px-3 text-[10.5px] font-bold uppercase tracking-[0.14em] text-white/40">
              {group.label}
            </div>
          )}
          {group.items.map(({ href, label, icon: Icon, exact }) => {
            const active = exact
              ? path === href
              : path === href || path.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                onClick={onNavigate}
                className={`relative mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] transition-colors ${
                  active
                    ? "bg-white/10 font-semibold text-white"
                    : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
              >
                {active && (
                  <span className="absolute -left-2.5 top-1.5 bottom-1.5 w-[3px] rounded bg-accent" />
                )}
                <Icon size={16} className="shrink-0 opacity-85" />
                {label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function UserFooter() {
  const { user, logout } = useAuth();
  return (
    <div className="space-y-2 border-t border-white/10 px-5 py-4">
      {user && (
        <>
          <div className="truncate text-xs font-semibold text-white/90">
            {user.name || user.email}
          </div>
          <div className="truncate text-xs text-white/40">{user.email}</div>
          <button
            onClick={logout}
            className="rounded-md border border-white/20 px-2.5 py-1 text-[11.5px] text-white/60 transition-colors hover:border-white/40 hover:text-white"
          >
            로그아웃
          </button>
        </>
      )}
      <div className="text-[11px] text-white/30">샘플 데이터 기반 · 참고용</div>
    </div>
  );
}

export default function Navbar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  // 라우트가 바뀌면 모바일 드로어 닫기
  useEffect(() => { setOpen(false); }, [path]);

  return (
    <>
      {/* 데스크톱 사이드바 */}
      <aside className="no-print fixed left-0 top-0 z-50 hidden h-full w-[236px] flex-col bg-brand text-white shadow-lg md:flex">
        <div className="border-b border-white/10 px-5 py-5">
          <Wordmark />
          <div className="mt-2 text-[11.5px] text-white/50">
            매물 탐색부터 계약·세금까지, 한 곳에서
          </div>
        </div>
        <NavList path={path} />
        <UserFooter />
      </aside>

      {/* 모바일 상단바 */}
      <div className="no-print sticky top-0 z-50 flex items-center justify-between bg-brand px-4 py-3 md:hidden">
        <Wordmark />
        <button
          onClick={() => setOpen(true)}
          aria-label="메뉴 열기"
          className="rounded-md p-1 text-white/80 hover:text-white"
        >
          <Menu size={22} />
        </button>
      </div>

      {/* 모바일 드로어 */}
      {open && (
        <div className="fixed inset-0 z-[60] md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute left-0 top-0 flex h-full w-[260px] flex-col bg-brand text-white shadow-xl">
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <Wordmark />
              <button
                onClick={() => setOpen(false)}
                aria-label="메뉴 닫기"
                className="rounded-md p-1 text-white/70 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>
            <NavList path={path} onNavigate={() => setOpen(false)} />
            <UserFooter />
          </div>
        </div>
      )}
    </>
  );
}
