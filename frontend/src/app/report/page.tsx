"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

type Comparable = { complex_name?: string; area_m2?: number; deal_price?: number; deal_date?: string; match_level?: string };
type AppraisalResult = {
  estimated_price?: number; low_price?: number; high_price?: number;
  asking_price?: number; gap_rate?: number; judgement?: string;
  confidence?: number; comparables?: Comparable[]; warnings?: string[];
  data_source?: string[];
};
type AnalysisResult = {
  cap_rate?: number; annual_income?: number; roi_5yr?: number;
  investment_grade?: string; appraisal_opinion?: string;
  strengths?: string[]; risk_factors?: string[]; recommendation?: string;
  price_per_pyeong?: number; regional_avg_per_pyeong?: number;
};

const MATCH_LABEL: Record<string, string> = {
  same_complex: "동일 단지", same_dong: "동일 동", same_gu: "동일 구",
  nearby: "인근", fallback: "폴백",
};

function fmt(n?: number) { return n ? n.toLocaleString("ko-KR") + "원" : "—"; }
function fmtPct(n?: number) { return n != null ? (n * 100).toFixed(1) + "%" : "—"; }

function MarkdownView({ text }: { text: string }) {
  if (!text) return null;
  const lines = text.split("\n");
  return (
    <div className="prose text-sm text-slate-700">
      {lines.map((line, i) => {
        if (line.startsWith("# ")) return <h1 key={i}>{line.slice(2)}</h1>;
        if (line.startsWith("## ")) return <h2 key={i}>{line.slice(3)}</h2>;
        if (line.startsWith("### ")) return <h3 key={i}>{line.slice(4)}</h3>;
        if (line.startsWith("> ")) return <blockquote key={i}>{line.slice(2)}</blockquote>;
        if (line.startsWith("- ")) return <li key={i}>{line.slice(2)}</li>;
        if (line.startsWith("| ")) return null; // skip tables
        if (line.trim() === "") return <div key={i} className="h-2" />;
        return <p key={i}>{line}</p>;
      })}
    </div>
  );
}

export default function ReportPage() {
  const [result, setResult]   = useState<Record<string, unknown> | null>(null);
  const [tab, setTab]         = useState(0);
  const [query, setQuery]     = useState("");

  useEffect(() => {
    const raw = sessionStorage.getItem("appraisalResult");
    const q   = sessionStorage.getItem("appraisalQuery");
    if (raw) setResult(JSON.parse(raw));
    if (q) setQuery(q);
  }, []);

  if (!result) {
    return (
      <div className="max-w-2xl mx-auto text-center py-20">
        <div className="text-4xl mb-4">📊</div>
        <p className="text-slate-500 mb-4">감정평가 결과가 없습니다.</p>
        <Link href="/appraisal" className="inline-block px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700">
          감정평가 시작하기
        </Link>
      </div>
    );
  }

  if (result.error) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-xl p-5">
          <h2 className="font-semibold text-red-700 mb-2">감정평가 실패</h2>
          <p className="text-sm text-red-600">{String(result.error)}</p>
        </div>
        <Link href="/appraisal" className="mt-4 inline-block text-sm text-blue-600 hover:underline">← 다시 시도</Link>
      </div>
    );
  }

  const ar = (result.analysis_result || {}) as AnalysisResult;
  const ro = (result.report_output as { structured?: AppraisalResult } | undefined);
  const ap: AppraisalResult = (ro?.structured) || {};
  const report = (result.final_report as string) || "";

  const TABS = ["📊 감정평가 결과", "🏠 비교 사례", "📈 투자 수익성", "📄 전체 리포트"];

  const verdictColor = (v?: string) => {
    if (!v) return "bg-gray-100 text-gray-700";
    if (v.includes("저평가")) return "bg-green-100 text-green-700";
    if (v.includes("고평가")) return "bg-red-100 text-red-700";
    return "bg-blue-100 text-blue-700";
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold">📊 감정평가 결과 리포트</h1>
          {query && <p className="text-sm text-slate-500 mt-1">"{query}"</p>}
        </div>
        <Link href="/appraisal" className="text-sm text-blue-600 hover:underline">← 새 감정평가</Link>
      </div>

      {/* 탭 */}
      <div className="flex border-b border-slate-200 mb-5 gap-1">
        {TABS.map((t, i) => (
          <button key={i} onClick={() => setTab(i)}
            className={`px-4 py-2 text-sm font-medium ${tab === i ? "tab-active" : "text-slate-500 hover:text-slate-700"}`}>
            {t}
          </button>
        ))}
      </div>

      {/* TAB 0: 감정평가 결과 */}
      {tab === 0 && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow p-5">
            <h2 className="font-semibold mb-3 text-slate-700">추정 시장가치</h2>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: "추정가", value: fmt(ap.estimated_price), highlight: true },
                { label: "범위", value: `${fmt(ap.low_price)} ~ ${fmt(ap.high_price)}` },
                { label: "호가", value: fmt(ap.asking_price) },
                { label: "괴리율", value: ap.gap_rate != null ? `${(ap.gap_rate * 100).toFixed(1)}%` : "—" },
              ].map(({ label, value, highlight }) => (
                <div key={label} className={`rounded-lg p-3 ${highlight ? "bg-blue-50" : "bg-slate-50"}`}>
                  <div className="text-xs text-slate-500">{label}</div>
                  <div className={`font-semibold mt-0.5 ${highlight ? "text-blue-700" : "text-slate-800"}`}>{value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow p-5">
            <h2 className="font-semibold mb-3 text-slate-700">고저평가 판단</h2>
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`px-4 py-1.5 rounded-full text-sm font-semibold ${verdictColor(ap.judgement)}`}>
                {ap.judgement || "—"}
              </span>
              <span className="text-sm text-slate-500">신뢰도: {ap.confidence != null ? `${(ap.confidence * 100).toFixed(0)}%` : "—"}</span>
            </div>
            {ap.warnings && ap.warnings.length > 0 && (
              <div className="mt-3 space-y-1">
                {ap.warnings.map((w, i) => <p key={i} className="text-xs text-amber-700 bg-amber-50 px-3 py-1.5 rounded">⚠️ {w}</p>)}
              </div>
            )}
          </div>

          {ar.price_per_pyeong && (
            <div className="bg-white rounded-xl shadow p-5">
              <h2 className="font-semibold mb-3 text-slate-700">단가 비교</h2>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="text-xs text-slate-500">평당가</div>
                  <div className="font-semibold">{(ar.price_per_pyeong * 10000).toLocaleString()}원/평</div>
                </div>
                {ar.regional_avg_per_pyeong && (
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500">지역 평균 평당가</div>
                    <div className="font-semibold">{(ar.regional_avg_per_pyeong * 10000).toLocaleString()}원/평</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 1: 비교 사례 */}
      {tab === 1 && (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          {ap.comparables && ap.comparables.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  {["단지명", "면적", "거래가", "거래일", "매칭 수준"].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-slate-600 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ap.comparables.map((c, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="px-4 py-3">{c.complex_name || "—"}</td>
                    <td className="px-4 py-3">{c.area_m2 ? `${c.area_m2.toFixed(1)}㎡` : "—"}</td>
                    <td className="px-4 py-3">{fmt(c.deal_price)}</td>
                    <td className="px-4 py-3">{c.deal_date || "—"}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">
                        {MATCH_LABEL[c.match_level || ""] || c.match_level || "—"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-12 text-slate-400">비교 사례 없음</div>
          )}
        </div>
      )}

      {/* TAB 2: 투자 수익성 */}
      {tab === 2 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "Cap Rate", value: ar.cap_rate ? `${ar.cap_rate}%` : "—" },
              { label: "연 임대수입 추정", value: ar.annual_income ? `${(ar.annual_income * 10000).toLocaleString()}원` : "—" },
              { label: "5년 예상 수익률", value: ar.roi_5yr ? `${ar.roi_5yr}%` : "—" },
              { label: "투자 등급", value: ar.investment_grade || "—" },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white rounded-xl shadow p-4">
                <div className="text-xs text-slate-500">{label}</div>
                <div className="font-bold text-lg mt-1 text-blue-700">{value}</div>
              </div>
            ))}
          </div>

          {ar.appraisal_opinion && (
            <div className="bg-white rounded-xl shadow p-5">
              <h2 className="font-semibold mb-2">감정평가 의견</h2>
              <p className="text-sm text-slate-700">{ar.appraisal_opinion}</p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {ar.strengths && ar.strengths.length > 0 && (
              <div className="bg-white rounded-xl shadow p-5">
                <h3 className="font-semibold mb-2 text-green-700">✅ 가치 상승 요인</h3>
                <ul className="space-y-1">{ar.strengths.map((s, i) => <li key={i} className="text-sm text-slate-700">• {s}</li>)}</ul>
              </div>
            )}
            {ar.risk_factors && ar.risk_factors.length > 0 && (
              <div className="bg-white rounded-xl shadow p-5">
                <h3 className="font-semibold mb-2 text-red-700">⚠️ 리스크 요인</h3>
                <ul className="space-y-1">{ar.risk_factors.map((r, i) => <li key={i} className="text-sm text-slate-700">• {r}</li>)}</ul>
              </div>
            )}
          </div>

          {ar.recommendation && (
            <div className="bg-blue-50 rounded-xl p-4 text-sm text-blue-800 font-medium">
              💡 {ar.recommendation}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: 전체 리포트 */}
      {tab === 3 && (
        <div className="bg-white rounded-xl shadow p-6">
          {report ? <MarkdownView text={report} /> : <p className="text-slate-400 text-sm">리포트 없음</p>}
        </div>
      )}
    </div>
  );
}
