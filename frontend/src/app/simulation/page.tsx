"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SimulationResult, SimulationRequest, ScenarioResult } from "@/lib/types";

const PROP_TYPES   = ["아파트", "오피스텔", "상가", "오피스", "공장", "토지"];
const REPAY_TYPES  = [
  { value: "equal_payment",   label: "원리금균등상환" },
  { value: "equal_principal", label: "원금균등상환" },
  { value: "interest_only",   label: "만기일시상환" },
];
const RENTAL_MODES = ["없음", "전세", "월세"];

function parsePrice(s: string): number {
  if (!s.trim()) return 0;
  const n = s
    .replace(/억/g, "00000000")
    .replace(/천만/g, "0000000")
    .replace(/천/g, "0000")
    .replace(/만/g, "0000")
    .replace(/[^0-9]/g, "");
  return n ? parseInt(n) : 0;
}

function fmt(n?: number) { return n != null ? n.toLocaleString("ko-KR") + "원" : "—"; }
function fmtPct(n?: number, deci = 2) { return n != null ? (n >= 0 ? "+" : "") + n.toFixed(deci) + "%" : "—"; }
function signLabel(n?: number) { return n == null ? "—" : n > 0 ? "▲" : n < 0 ? "▼" : "─"; }

export default function SimulationPage() {
  // 입력 상태
  const [purchasePriceStr, setPurchasePriceStr] = useState("");
  const [propType, setPropType]     = useState("아파트");
  const [loanRatio, setLoanRatio]   = useState(50);
  const [interestRate, setInterestRate] = useState(4.0);
  const [loanYears, setLoanYears]   = useState(30);
  const [repayType, setRepayType]   = useState("equal_payment");
  const [holdingYears, setHoldingYears] = useState(3);
  const [growthRate, setGrowthRate] = useState(0);
  const [rentalMode, setRentalMode] = useState("없음");
  const [depositStr, setDepositStr] = useState("");
  const [rentFeeStr, setRentFeeStr] = useState("");
  const [mgmtFeeStr, setMgmtFeeStr] = useState("");
  const [ownedHomes, setOwnedHomes] = useState(1);

  const [result, setResult] = useState<SimulationResult | null>(null);
  const [report, setReport] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState("");
  const [tab, setTab]       = useState(0);

  // 추천 페이지에서 매물 자동입력
  useEffect(() => {
    const raw = sessionStorage.getItem("simFromListing");
    if (raw) {
      const l = JSON.parse(raw);
      if (l.asking_price) setPurchasePriceStr(String(Math.round(l.asking_price / 10000)) + "만");
      if (l.property_type) {
        const map: Record<string,string> = { 주거용: "아파트", 상업용: "상가", 업무용: "오피스", 산업용: "공장" };
        setPropType(map[l.property_type] || l.property_type);
      }
      if (l.deposit_price) { setRentalMode("전세"); setDepositStr(String(Math.round(l.deposit_price / 10000)) + "만"); }
      if (l.maintenance_fee) setMgmtFeeStr(String(l.maintenance_fee));
      sessionStorage.removeItem("simFromListing");
    }
  }, []);

  const handleSubmit = async () => {
    const purchasePrice = parsePrice(purchasePriceStr);
    if (!purchasePrice) { setError("매수가를 입력해주세요."); return; }
    setError("");
    setLoading(true);
    try {
      const params: SimulationRequest = {
        purchase_price: purchasePrice,
        loan_ratio: loanRatio / 100,
        annual_interest_rate: interestRate,
        loan_years: loanYears,
        repayment_type: repayType as SimulationRequest["repayment_type"],
        holding_years: holdingYears,
        expected_annual_growth_rate: growthRate,
        property_type: propType,
        owned_homes: ownedHomes,
        rent_deposit: rentalMode === "전세" && depositStr ? parsePrice(depositStr) : undefined,
        rent_fee: rentalMode === "월세" && rentFeeStr ? parseInt(rentFeeStr) : undefined,
        monthly_management_fee: mgmtFeeStr ? parseInt(mgmtFeeStr) : undefined,
      };
      const res = await api.simulation(params) as { result?: SimulationResult; report?: string; error?: string };
      if (res.error) throw new Error(res.error);
      setResult(res.result || null);
      setReport(res.report || "");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "시뮬레이션 실패");
    } finally {
      setLoading(false);
    }
  };

  const verdictStyle = (aroi?: number) => {
    if (!aroi) return "bg-gray-100 text-gray-700";
    if (aroi >= 10) return "bg-green-100 text-green-700";
    if (aroi >= 5)  return "bg-yellow-100 text-yellow-700";
    if (aroi >= 0)  return "bg-orange-100 text-orange-700";
    return "bg-red-100 text-red-700";
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">📈 투자 시뮬레이션</h1>
      <p className="text-slate-500 text-sm mb-5">부동산 투자 조건을 입력하면 수익성을 계산합니다.</p>
      <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-3 py-2 rounded-lg mb-5">
        ⚠️ 이 시뮬레이션은 간이 계산입니다. 실제 세율·대출 조건은 다를 수 있습니다.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 왼쪽: 매수·대출 */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow p-5">
            <h2 className="font-semibold mb-4 text-slate-700">매수 조건</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">매수가 *</label>
                <input className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="예: 7억5천, 750000만"
                  value={purchasePriceStr} onChange={e => setPurchasePriceStr(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">매물 유형</label>
                <select className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" value={propType} onChange={e => setPropType(e.target.value)}>
                  {PROP_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">보유 주택 수 (취득 전)</label>
                <input type="number" min={1} max={10} className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                  value={ownedHomes} onChange={e => setOwnedHomes(Number(e.target.value))} />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow p-5">
            <h2 className="font-semibold mb-4 text-slate-700">대출 조건</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">대출 비율: {loanRatio}%</label>
                <input type="range" min={0} max={90} step={5} value={loanRatio} onChange={e => setLoanRatio(Number(e.target.value))} className="w-full" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">연 이율: {interestRate}%</label>
                <input type="range" min={0} max={15} step={0.1} value={interestRate}
                  onChange={e => setInterestRate(parseFloat(Number(e.target.value).toFixed(1)))} className="w-full" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">대출 기간: {loanYears}년</label>
                <input type="range" min={10} max={40} step={5} value={loanYears} onChange={e => setLoanYears(Number(e.target.value))} className="w-full" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">상환 방식</label>
                <select className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" value={repayType} onChange={e => setRepayType(e.target.value)}>
                  {REPAY_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* 오른쪽: 보유·임대 */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow p-5">
            <h2 className="font-semibold mb-4 text-slate-700">보유 계획</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">보유 기간: {holdingYears}년</label>
                <input type="range" min={1} max={20} value={holdingYears} onChange={e => setHoldingYears(Number(e.target.value))} className="w-full" />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">예상 연 상승률: {growthRate >= 0 ? "+" : ""}{growthRate}%</label>
                <input type="range" min={-10} max={20} step={0.5} value={growthRate}
                  onChange={e => setGrowthRate(parseFloat(Number(e.target.value).toFixed(1)))} className="w-full" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow p-5">
            <h2 className="font-semibold mb-4 text-slate-700">임대 수입</h2>
            <div className="space-y-3">
              <div className="flex gap-2">
                {RENTAL_MODES.map(m => (
                  <button key={m} onClick={() => setRentalMode(m)}
                    className={`flex-1 py-1.5 text-sm rounded-lg border ${rentalMode === m ? "bg-blue-600 text-white border-blue-600" : "border-slate-300 text-slate-600 hover:bg-slate-50"}`}>
                    {m}
                  </button>
                ))}
              </div>
              {rentalMode === "전세" && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1">전세 보증금</label>
                  <input className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="예: 3억"
                    value={depositStr} onChange={e => setDepositStr(e.target.value)} />
                </div>
              )}
              {rentalMode === "월세" && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1">월세 (원)</label>
                  <input type="number" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="예: 1500000"
                    value={rentFeeStr} onChange={e => setRentFeeStr(e.target.value)} />
                </div>
              )}
              <div>
                <label className="block text-xs text-slate-500 mb-1">월 관리비 (원)</label>
                <input type="number" className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm" placeholder="예: 200000"
                  value={mgmtFeeStr} onChange={e => setMgmtFeeStr(e.target.value)} />
              </div>
            </div>
          </div>

          {error && <p className="text-red-500 text-sm">⚠️ {error}</p>}
          <button onClick={handleSubmit} disabled={loading}
            className="w-full py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 disabled:opacity-50">
            {loading ? "계산 중..." : "💰 시뮬레이션 계산"}
          </button>
        </div>
      </div>

      {/* 결과 */}
      {result && (
        <div className="mt-6">
          <div className="flex border-b border-slate-200 mb-4 gap-1">
            {["📊 대시보드", "📄 리포트"].map((t, i) => (
              <button key={i} onClick={() => setTab(i)}
                className={`px-4 py-2 text-sm font-medium ${tab === i ? "tab-active" : "text-slate-500 hover:text-slate-700"}`}>{t}</button>
            ))}
          </div>

          {tab === 0 && (
            <div className="space-y-4">
              {/* 핵심 지표 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: "매수가", value: fmt(result.purchase_price) },
                  { label: "대출금", value: fmt(result.loan_amount) },
                  { label: "필요 현금", value: fmt(result.required_cash) },
                  { label: "실투자금", value: fmt(result.equity) },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-white rounded-xl shadow p-4">
                    <div className="text-xs text-slate-400">{label}</div>
                    <div className="font-bold mt-1 text-blue-700">{value}</div>
                  </div>
                ))}
              </div>

              {/* 취득 비용 + 대출 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white rounded-xl shadow p-5">
                  <h3 className="font-semibold mb-3">취득 비용</h3>
                  <table className="w-full text-sm">
                    <tbody>
                      {[
                        ["취득세", fmt(result.acquisition_cost.acquisition_tax)],
                        ["중개보수", fmt(result.acquisition_cost.brokerage_fee)],
                        ["기타", fmt(result.acquisition_cost.other_cost)],
                        ["합계", fmt(result.acquisition_cost.total)],
                      ].map(([k, v]) => (
                        <tr key={k} className="border-b border-slate-100 last:font-semibold">
                          <td className="py-1.5 text-slate-500">{k}</td>
                          <td className="py-1.5 text-right">{v}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {result.loan_amount > 0 && (
                  <div className="bg-white rounded-xl shadow p-5">
                    <h3 className="font-semibold mb-3">대출 정보</h3>
                    <table className="w-full text-sm">
                      <tbody>
                        {[
                          ["월 상환액", fmt(result.loan.monthly_payment)],
                          ["총 상환액", fmt(result.loan.total_repayment)],
                          ["총 이자", fmt(result.loan.total_interest)],
                        ].map(([k, v]) => (
                          <tr key={k} className="border-b border-slate-100 last:font-semibold">
                            <td className="py-1.5 text-slate-500">{k}</td>
                            <td className="py-1.5 text-right">{v}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* 시나리오 */}
              <div className="bg-white rounded-xl shadow overflow-hidden">
                <h3 className="font-semibold p-4 pb-0">시나리오 비교</h3>
                <table className="w-full text-sm mt-3">
                  <thead className="bg-slate-50">
                    <tr>
                      {["지표", "비관", "기본", "낙관"].map(h => (
                        <th key={h} className="px-4 py-3 text-left font-semibold text-slate-600">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(
                      [
                        ["연 상승률",      (s: ScenarioResult) => `${s.annual_growth_rate.toFixed(1)}%`],
                        ["예상 매도가",    (s: ScenarioResult) => fmt(s.expected_sale_price)],
                        ["시세 차익",      (s: ScenarioResult) => `${signLabel(s.capital_gain)} ${fmt(Math.abs(s.capital_gain))}`],
                        ["순손익",         (s: ScenarioResult) => `${signLabel(s.net_profit)} ${fmt(Math.abs(s.net_profit))}`],
                        ["자기자본 수익률",(s: ScenarioResult) => fmtPct(s.equity_roi)],
                        ["연환산 수익률",  (s: ScenarioResult) => fmtPct(s.annual_equity_roi)],
                      ] as [string, (s: ScenarioResult) => string][]
                    ).map(([label, getter]) => (
                      <tr key={label}>
                        <td className="px-4 py-2.5 text-slate-500">{label}</td>
                        <td className="px-4 py-2.5 text-red-600">{getter(result.scenario_bear)}</td>
                        <td className="px-4 py-2.5 font-medium">{getter(result.scenario_base)}</td>
                        <td className="px-4 py-2.5 text-green-600">{getter(result.scenario_bull)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 투자 판단 */}
              <div className={`rounded-xl p-4 font-semibold text-center ${verdictStyle(result.scenario_base.annual_equity_roi)}`}>
                {result.scenario_base.annual_equity_roi >= 10 && "✅ 우수한 투자 수익률 (연 10% 이상)"}
                {result.scenario_base.annual_equity_roi >= 5 && result.scenario_base.annual_equity_roi < 10 && "🟡 양호한 투자 수익률 (연 5~10%)"}
                {result.scenario_base.annual_equity_roi >= 0 && result.scenario_base.annual_equity_roi < 5 && "🟠 낮은 수익률 (연 0~5%)"}
                {result.scenario_base.annual_equity_roi < 0 && "🔴 마이너스 수익률 — 투자 재검토 필요"}
              </div>
            </div>
          )}

          {tab === 1 && (
            <div className="bg-white rounded-xl shadow p-6 prose text-sm text-slate-700 whitespace-pre-wrap">{report}</div>
          )}
        </div>
      )}
    </div>
  );
}
