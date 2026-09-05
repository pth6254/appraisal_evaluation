"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, Landmark, Scale, WalletCards } from "lucide-react";
import { api } from "@/lib/api";
import type { CaseCandidateComparison, CaseCandidateComparisonRow, PurchaseCase } from "@/lib/types";

function won(value: number | null | undefined): string {
  return value == null ? "미확인" : `${Math.round(value / 10_000).toLocaleString()}만원`;
}
function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function textValue(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

export default function CaseComparisonPage() {
  const caseId = Number(useParams<{ id: string }>().id);
  const [caseItem, setCaseItem] = useState<PurchaseCase | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [comparison, setComparison] = useState<CaseCandidateComparison | null>(null);
  const [decisionTarget, setDecisionTarget] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const compare = async (ids: number[]) => {
    if (ids.length < 2) { setComparison(null); return; }
    setComparison(await api.caseComparison(caseId, ids));
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const value = await api.caseOne(caseId);
        if (cancelled) return;
        const defaults = (value.properties ?? []).filter((property) => property.status !== "rejected").slice(0, 4).map((property) => property.id);
        setCaseItem(value);
        setSelectedIds(defaults);
        if (defaults.length >= 2) setComparison(await api.caseComparison(caseId, defaults));
      } catch { if (!cancelled) setError("후보 비교 정보를 불러오지 못했습니다."); }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [caseId]);

  const toggleCandidate = async (propertyId: number) => {
    const next = selectedIds.includes(propertyId)
      ? selectedIds.filter((id) => id !== propertyId)
      : selectedIds.length < 4 ? [...selectedIds, propertyId] : selectedIds;
    if (next === selectedIds) { setError("후보는 최대 4개까지 비교할 수 있습니다."); return; }
    setError(""); setSelectedIds(next);
    try { await compare(next); } catch { setError("후보 비교 결과를 갱신하지 못했습니다."); }
  };

  const decide = async () => {
    if (decisionTarget == null || reason.trim().length < 3) { setError("선택 근거를 3자 이상 입력해주세요."); return; }
    try {
      await api.selectCaseCandidate(caseId, decisionTarget, reason.trim());
      const refreshed = await api.caseOne(caseId);
      setCaseItem(refreshed);
      await compare(selectedIds);
      setDecisionTarget(null); setReason(""); setError("");
    } catch { setError("최종 후보를 저장하지 못했습니다."); }
  };

  if (loading) return <div className="py-20 text-center text-slate-400">비교 정보를 불러오는 중...</div>;
  if (!caseItem) return <div className="py-20 text-center text-slate-500">케이스를 찾을 수 없습니다.</div>;
  const properties = caseItem.properties ?? [];

  return <div className="mx-auto max-w-7xl space-y-5">
    <div><Link href={`/cases/${caseId}`} className="text-sm font-medium text-primary hover:underline">← 검토 워크스페이스</Link><h1 className="mt-3 text-2xl font-bold">{caseItem.title} 후보 비교</h1><p className="mt-1 text-sm text-slate-500">점수 하나로 순위를 정하지 않고 가격·자금·권리·검토 상태를 각각 비교합니다.</p></div>

    <section className="rounded-2xl border bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between"><h2 className="font-bold">비교 후보 선택</h2><span className="text-xs text-slate-500">{selectedIds.length}/4개 선택</span></div>
      <div className="mt-3 flex flex-wrap gap-2">{properties.map((property) => <button key={property.id} onClick={() => toggleCandidate(property.id)} className={`rounded-full border px-3 py-1.5 text-sm ${selectedIds.includes(property.id) ? "border-primary bg-emerald-50 font-semibold text-primary" : "border-slate-200 text-slate-500"}`}>{property.name}{property.status === "rejected" ? " · 제외됨" : ""}</button>)}</div>
      {selectedIds.length < 2 && <p className="mt-3 text-xs text-amber-700">비교하려면 후보를 2개 이상 선택해주세요.</p>}
    </section>
    {error && <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">{error}</p>}

    {comparison && <>
      <section className="overflow-x-auto rounded-2xl border bg-white shadow-sm">
        <table className="w-full min-w-[900px] text-sm"><thead className="bg-slate-50"><tr><th className="w-40 px-4 py-3 text-left">비교 항목</th>{comparison.rows.map((row) => <th key={row.property_id} className="px-4 py-3 text-left"><span>{row.name}</span>{comparison.selected_property_id === row.property_id && <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">최종 선택</span>}<p className="mt-1 font-normal text-slate-400">{row.address || "주소 미입력"}</p></th>)}</tr></thead>
          <tbody className="divide-y">{[
            ["희망가", (row: CaseCandidateComparisonRow) => won(row.asking_price)],
            ["AI 추정가", (row: CaseCandidateComparisonRow) => won(row.estimated_value)],
            ["추정가 차이", (row: CaseCandidateComparisonRow) => row.price_gap_ratio == null ? "미확인" : `${row.price_gap_ratio > 0 ? "+" : ""}${row.price_gap_ratio}%`],
            ["필요 대출", (row: CaseCandidateComparisonRow) => won(numberValue(row.funding?.loan_amount))],
            ["적용 금리", (row: CaseCandidateComparisonRow) => numberValue(row.funding?.annual_interest_rate) == null ? "미확인" : `${numberValue(row.funding?.annual_interest_rate)}%`],
            ["권리 위험", (row: CaseCandidateComparisonRow) => textValue(row.rights?.risk_label) ?? textValue(row.rights?.risk_grade) ?? "서류 필요"],
            ["분석 최신성", (row: CaseCandidateComparisonRow) => Object.values(row.analysis_status).some((status) => status === "stale") ? "갱신 필요" : Object.values(row.analysis_status).some((status) => status === "missing") ? "자료 부족" : "최신"],
            ["검토 완료율", (row: CaseCandidateComparisonRow) => `${row.review_progress}%`],
          ].map(([label, get]) => <tr key={String(label)}><td className="px-4 py-3 font-medium text-slate-500">{String(label)}</td>{comparison.rows.map((row) => <td key={row.property_id} className="px-4 py-3 font-semibold">{(get as (row: CaseCandidateComparisonRow) => string)(row)}</td>)}</tr>)}</tbody>
        </table>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">{comparison.rows.map((row) => <article key={row.property_id} className={`rounded-2xl border bg-white p-5 shadow-sm ${comparison.selected_property_id === row.property_id ? "ring-2 ring-primary" : ""}`}>
        <div className="flex items-start justify-between"><div><h2 className="font-bold">{row.name}</h2><p className="mt-1 text-xs text-slate-500">검토 완료 {row.review_progress}%</p></div>{row.decision_ready ? <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-xs text-emerald-700"><CheckCircle2 size={13} />필수 검토 완료</span> : <span className="flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600"><CircleHelp size={13} />확인 필요</span>}</div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-xs"><div className="rounded-lg bg-slate-50 p-3"><Landmark size={15} className="mb-2 text-primary" /><span className="text-slate-400">가격 차이</span><strong className="mt-1 block">{row.price_gap_ratio == null ? "미확인" : `${row.price_gap_ratio}%`}</strong></div><div className="rounded-lg bg-slate-50 p-3"><WalletCards size={15} className="mb-2 text-primary" /><span className="text-slate-400">대출금</span><strong className="mt-1 block">{won(numberValue(row.funding?.loan_amount))}</strong></div><div className="rounded-lg bg-slate-50 p-3"><Scale size={15} className="mb-2 text-primary" /><span className="text-slate-400">권리등급</span><strong className="mt-1 block">{textValue(row.rights?.risk_label) ?? "미확인"}</strong></div></div>
        {row.highlights.length > 0 && <div className="mt-4 space-y-1 text-xs text-emerald-700">{row.highlights.map((value) => <p key={value} className="flex gap-2"><CheckCircle2 size={14} />{value}</p>)}</div>}
        {row.warnings.length > 0 && <div className="mt-4 space-y-1 text-xs text-amber-700">{row.warnings.map((value) => <p key={value} className="flex gap-2"><AlertTriangle size={14} />{value}</p>)}</div>}
        {row.missing.length > 0 && <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600"><strong>아직 필요한 정보</strong><ul className="mt-1 list-inside list-disc">{row.missing.map((value) => <li key={value}>{value}</li>)}</ul></div>}
        <button onClick={() => { setDecisionTarget(row.property_id); setReason(comparison.selected_property_id === row.property_id ? comparison.decision_reason : ""); }} className="mt-4 w-full rounded-lg border border-primary py-2 text-sm font-semibold text-primary hover:bg-emerald-50">이 후보를 최종 선택</button>
      </article>)}</section>

      {decisionTarget != null && <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5"><h2 className="font-bold">최종 후보 선택 근거</h2><p className="mt-1 text-xs text-slate-600">미확인 항목이 있어도 선택할 수 있지만, 경고와 누락 자료를 확인한 근거를 남겨주세요.</p><textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} placeholder="예: 예산 범위 안이며 권리분석이 안전하고 출퇴근 조건이 가장 적합함" className="mt-3 w-full rounded-lg border border-emerald-200 p-3 text-sm" /><div className="mt-3 flex justify-end gap-2"><button onClick={() => { setDecisionTarget(null); setReason(""); }} className="rounded-lg border px-4 py-2 text-sm">취소</button><button onClick={decide} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white">선택 저장</button></div></section>}
    </>}
  </div>;
}
