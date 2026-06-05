"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { HistoryItem } from "@/lib/types";

const FEATURES = [
  {
    href: "/appraisal",
    icon: "🏠",
    title: "부동산 감정평가",
    desc: "AI가 실거래가 기반으로 시장가치를 분석합니다",
    border: "border-blue-200",
    bg: "bg-blue-50 hover:bg-blue-100",
    label: "text-blue-700",
  },
  {
    href: "/recommendation",
    icon: "✨",
    title: "매물 추천",
    desc: "조건에 맞는 최적의 매물을 찾아드립니다",
    border: "border-violet-200",
    bg: "bg-violet-50 hover:bg-violet-100",
    label: "text-violet-700",
  },
  {
    href: "/simulation",
    icon: "📈",
    title: "투자 시뮬레이션",
    desc: "수익성을 다양한 시나리오로 미리 검토합니다",
    border: "border-emerald-200",
    bg: "bg-emerald-50 hover:bg-emerald-100",
    label: "text-emerald-700",
  },
  {
    href: "/comparison",
    icon: "⚖️",
    title: "매물 비교",
    desc: "여러 매물을 점수 기준으로 한눈에 비교합니다",
    border: "border-orange-200",
    bg: "bg-orange-50 hover:bg-orange-100",
    label: "text-orange-700",
  },
  {
    href: "/dashboard",
    icon: "📋",
    title: "이력 대시보드",
    desc: "과거 감정평가 이력과 통계를 확인합니다",
    border: "border-slate-200",
    bg: "bg-slate-50 hover:bg-slate-100",
    label: "text-slate-700",
  },
];

const VERDICT_STYLE: Record<string, string> = {
  저평가: "bg-green-100 text-green-700",
  고평가: "bg-red-100 text-red-700",
  적정가: "bg-blue-100 text-blue-700",
};

export default function HomePage() {
  const { user } = useAuth();
  const [recent, setRecent] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  useEffect(() => {
    api.history(5, 0, "")
      .then(res => setRecent(res.items as HistoryItem[]))
      .catch(() => {})
      .finally(() => setLoadingHistory(false));
  }, []);

  const today = new Date().toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  const displayName =
    user?.name ||
    (user?.email ? user.email.split("@")[0] : null) ||
    "회원";

  return (
    <div className="max-w-4xl mx-auto space-y-7">

      {/* ── 환영 배너 ── */}
      <div className="rounded-2xl bg-gradient-to-br from-slate-800 via-slate-800 to-blue-900 px-8 py-7 text-white shadow-lg">
        <p className="text-xs text-blue-300 mb-2 tracking-wide">{today}</p>
        <h1 className="text-2xl font-bold mb-1">
          안녕하세요, {displayName}님 👋
        </h1>
        <p className="text-sm text-slate-300">
          AI 기반 부동산 감정평가 시스템입니다. 아래 서비스를 바로 시작해 보세요.
        </p>
      </div>

      {/* ── 주요 서비스 카드 ── */}
      <section>
        <h2 className="text-xs font-bold text-slate-400 tracking-widest uppercase mb-3">
          주요 서비스
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {FEATURES.map(({ href, icon, title, desc, border, bg, label }) => (
            <Link
              key={href}
              href={href}
              className={`group flex flex-col gap-3 rounded-xl border-2 p-5 transition-colors ${border} ${bg}`}
            >
              <span className="text-2xl leading-none">{icon}</span>
              <div className="flex-1">
                <p className={`font-semibold text-sm ${label}`}>{title}</p>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">{desc}</p>
              </div>
              <span className={`text-xs font-semibold ${label} group-hover:underline`}>
                시작하기 →
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── 최근 감정평가 이력 ── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold text-slate-400 tracking-widest uppercase">
            최근 감정평가 이력
          </h2>
          {recent.length > 0 && (
            <Link href="/dashboard" className="text-xs text-blue-600 hover:underline">
              전체 보기 →
            </Link>
          )}
        </div>

        {loadingHistory ? (
          <div className="bg-white rounded-xl shadow p-6 text-center text-sm text-slate-400">
            불러오는 중...
          </div>
        ) : recent.length === 0 ? (
          <div className="rounded-xl border-2 border-dashed border-slate-200 bg-white p-10 text-center">
            <p className="text-slate-400 text-sm mb-5">아직 감정평가 이력이 없습니다.</p>
            <Link
              href="/appraisal"
              className="inline-block px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors"
            >
              첫 감정평가 시작하기 →
            </Link>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  {["물건 정보", "유형", "추정가", "판정", "등급", "일시"].map(h => (
                    <th
                      key={h}
                      className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {recent.map(it => (
                  <tr key={it.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 max-w-[200px] truncate text-slate-800">
                      {it.query}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {it.category || "—"}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">
                      {it.estimated_value
                        ? Math.round(it.estimated_value / 10_000).toLocaleString("ko-KR") + "만원"
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {it.valuation_verdict ? (
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            VERDICT_STYLE[it.valuation_verdict] || "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {it.valuation_verdict}
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-700 font-medium">
                      {it.investment_grade || "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {it.created?.slice(0, 10) || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── 하단 안내 ── */}
      <p className="text-center text-xs text-slate-400 pb-4">
        ⚠️ 본 시스템은 AI 기반 참고용 분석 도구입니다. 실제 투자 결정 시 전문가 자문을 받으세요.
      </p>
    </div>
  );
}
