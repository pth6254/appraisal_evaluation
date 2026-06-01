"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { RecommendationResult } from "@/lib/types";

const REGIONS    = ["전체", "강남구", "마포구", "서초구", "송파구", "용산구", "성동구", "강동구", "영등포구"];
const PROP_TYPES = ["전체", "주거용", "상업용", "업무용", "산업용", "토지"];
const PURPOSES   = ["전체", "실거주", "투자", "매도", "보유"];

function parsePrice(s: string): number | undefined {
  if (!s.trim()) return undefined;
  const n = s
    .replace(/억/g, "00000000")
    .replace(/천만/g, "0000000")
    .replace(/천/g, "0000")
    .replace(/만/g, "0000")
    .replace(/[^0-9]/g, "");
  return n ? parseInt(n) : undefined;
}

function ScoreBar({ score, max = 10 }: { score?: number; max?: number }) {
  const pct = ((score || 0) / max) * 100;
  const color = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-100 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-500 w-6">{score?.toFixed(1) || "—"}</span>
    </div>
  );
}

export default function RecommendationPage() {
  const router = useRouter();
  const [region, setRegion]   = useState("전체");
  const [propType, setPropType] = useState("전체");
  const [purpose, setPurpose] = useState("전체");
  const [budgetMin, setBudgetMin] = useState("");
  const [budgetMax, setBudgetMax] = useState("");
  const [area, setArea]       = useState("");
  const [limit, setLimit]     = useState(5);
  const [results, setResults] = useState<RecommendationResult[]>([]);
  const [report, setReport]   = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [tab, setTab]         = useState(0);
  const [basket, setBasket]   = useState<RecommendationResult[]>([]);

  const handleSubmit = async () => {
    setError("");
    setLoading(true);
    setResults([]);
    try {
      const res = await api.recommendation({
        region:        region === "전체" ? undefined : region,
        property_type: propType === "전체" ? undefined : propType,
        purpose:       purpose === "전체" ? undefined : purpose,
        budget_min:    parsePrice(budgetMin),
        budget_max:    parsePrice(budgetMax),
        area_m2:       area ? parseFloat(area) : undefined,
        limit,
      }) as { results?: RecommendationResult[]; report?: string; error?: string };

      if (res.error) throw new Error(res.error);
      setResults(res.results || []);
      setReport(res.report || "");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "추천 실패");
    } finally {
      setLoading(false);
    }
  };

  const addToBasket = (r: RecommendationResult) => {
    if (basket.find(b => b.listing.listing_id === r.listing.listing_id)) return;
    if (basket.length >= 5) { alert("최대 5개까지 비교 가능합니다."); return; }
    const next = [...basket, r];
    setBasket(next);
    sessionStorage.setItem("comparisonBasket", JSON.stringify(next));
  };

  const simFromListing = (r: RecommendationResult) => {
    sessionStorage.setItem("simFromListing", JSON.stringify(r.listing));
    router.push("/simulation");
  };

  const goCompare = () => router.push("/comparison");

  const fmt = (n?: number) => n ? n.toLocaleString("ko-KR") + "원" : "—";

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-start gap-6">
        {/* 메인 */}
        <div className="flex-1">
          <h1 className="text-2xl font-bold mb-1">✨ 매물 추천</h1>
          <p className="text-slate-500 text-sm mb-5">조건을 입력하면 AI가 최적 매물을 추천합니다.</p>

          {/* 검색 폼 */}
          <div className="bg-white rounded-xl shadow p-5 mb-5">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-xs text-slate-500 mb-1">지역</label>
                <select className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" value={region} onChange={e => setRegion(e.target.value)}>
                  {REGIONS.map(r => <option key={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">매물 유형</label>
                <select className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" value={propType} onChange={e => setPropType(e.target.value)}>
                  {PROP_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">투자 목적</label>
                <select className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" value={purpose} onChange={e => setPurpose(e.target.value)}>
                  {PURPOSES.map(p => <option key={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">예산 최소 (예: 5억)</label>
                <input className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="예: 3억" value={budgetMin} onChange={e => setBudgetMin(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">예산 최대 (예: 10억)</label>
                <input className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="예: 10억" value={budgetMax} onChange={e => setBudgetMax(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">면적 (㎡)</label>
                <input className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="예: 84" value={area} onChange={e => setArea(e.target.value)} />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-xs text-slate-500">추천 수</label>
                <input type="range" min={1} max={10} value={limit} onChange={e => setLimit(Number(e.target.value))} className="w-24" />
                <span className="text-sm font-medium text-blue-700">{limit}개</span>
              </div>
              <button onClick={handleSubmit} disabled={loading}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 disabled:opacity-50">
                {loading ? "추천 분석 중..." : "🔍 매물 추천받기"}
              </button>
            </div>
            {error && <p className="text-red-500 text-sm mt-2">⚠️ {error}</p>}
          </div>

          {/* 결과 탭 */}
          {results.length > 0 && (
            <>
              <div className="flex border-b border-slate-200 mb-4 gap-1">
                {["🏠 추천 카드", "📄 리포트"].map((t, i) => (
                  <button key={i} onClick={() => setTab(i)}
                    className={`px-4 py-2 text-sm font-medium ${tab === i ? "tab-active" : "text-slate-500 hover:text-slate-700"}`}>
                    {t}
                  </button>
                ))}
              </div>

              {tab === 0 && (
                <div className="space-y-4">
                  {results.map((r, i) => (
                    <div key={r.listing.listing_id} className="bg-white rounded-xl shadow p-5 border-l-4 border-blue-500">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <span className="text-xs text-blue-600 font-bold bg-blue-50 px-2 py-0.5 rounded-full">{i + 1}위</span>
                          <span className={`ml-2 text-xs px-2 py-0.5 rounded-full font-medium ${
                            r.total_score >= 7 ? "bg-green-100 text-green-700" :
                            r.total_score >= 5 ? "bg-yellow-100 text-yellow-700" : "bg-red-100 text-red-700"
                          }`}>{r.recommendation_label || "—"}</span>
                          <h3 className="font-bold mt-1">{r.listing.complex_name || r.listing.address}</h3>
                          <p className="text-xs text-slate-400">{r.listing.address}</p>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-blue-700">{fmt(r.listing.asking_price)}</div>
                          {r.listing.area_m2 && <div className="text-xs text-slate-400">{r.listing.area_m2.toFixed(1)}㎡</div>}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 mb-3 text-xs text-slate-500">
                        {r.listing.floor && <span>🏢 {r.listing.floor}층</span>}
                        {r.listing.built_year && <span>🏗️ {r.listing.built_year}년</span>}
                        {r.listing.station_distance_m && <span>🚇 {r.listing.station_distance_m}m</span>}
                        {r.listing.deposit_price && <span>💰 보증금 {fmt(r.listing.deposit_price)}</span>}
                      </div>

                      {/* 점수 바 */}
                      <div className="space-y-1.5 mb-3">
                        {[
                          { label: "가격", score: r.price_score },
                          { label: "입지", score: r.location_score },
                          { label: "투자", score: r.investment_score },
                          { label: "리스크", score: r.risk_score },
                        ].map(({ label, score }) => (
                          <div key={label} className="flex items-center gap-2 text-xs">
                            <span className="w-10 text-slate-500">{label}</span>
                            <ScoreBar score={score} />
                          </div>
                        ))}
                      </div>

                      {r.reasons && r.reasons.length > 0 && (
                        <div className="mb-2">
                          {r.reasons.map((rn, j) => <span key={j} className="inline-block text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded mr-1 mb-1">✅ {rn}</span>)}
                        </div>
                      )}
                      {r.risks && r.risks.length > 0 && (
                        <div className="mb-3">
                          {r.risks.map((rk, j) => <span key={j} className="inline-block text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded mr-1 mb-1">⚠️ {rk}</span>)}
                        </div>
                      )}

                      <div className="flex gap-2">
                        <button onClick={() => simFromListing(r)}
                          className="flex-1 py-1.5 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-lg hover:bg-blue-100">
                          📈 시뮬레이션
                        </button>
                        <button onClick={() => addToBasket(r)}
                          disabled={!!basket.find(b => b.listing.listing_id === r.listing.listing_id)}
                          className="flex-1 py-1.5 text-xs bg-slate-50 text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-100 disabled:opacity-40">
                          {basket.find(b => b.listing.listing_id === r.listing.listing_id) ? "✓ 바구니 담김" : "➕ 비교 바구니"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {tab === 1 && (
                <div className="bg-white rounded-xl shadow p-6 prose text-sm text-slate-700 whitespace-pre-wrap">
                  {report || "리포트 없음"}
                </div>
              )}
            </>
          )}
        </div>

        {/* 비교 바구니 사이드바 */}
        {basket.length > 0 && (
          <div className="w-56 shrink-0">
            <div className="bg-white rounded-xl shadow p-4 sticky top-6">
              <h3 className="font-semibold text-sm mb-3">⚖️ 비교 바구니 ({basket.length})</h3>
              <div className="space-y-2 mb-3">
                {basket.map(b => (
                  <div key={b.listing.listing_id} className="text-xs bg-slate-50 rounded p-2">
                    <div className="font-medium truncate">{b.listing.complex_name || b.listing.address}</div>
                    <div className="text-slate-400">{(b.listing.asking_price / 100000000).toFixed(1)}억</div>
                  </div>
                ))}
              </div>
              <button onClick={goCompare}
                className="w-full py-2 bg-blue-600 text-white text-xs rounded-lg font-semibold hover:bg-blue-700">
                비교 분석 시작
              </button>
              <button onClick={() => { setBasket([]); sessionStorage.removeItem("comparisonBasket"); }}
                className="w-full py-1.5 text-xs text-slate-400 mt-1 hover:text-slate-600">
                바구니 초기화
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
