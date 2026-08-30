"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, FileSearch, MapPinned, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { setSessionValue } from "@/lib/sessionStore";
import type { CandidateAnalysis, CaseProperty, HistoryItem, PurchaseCase, PurchaseCaseStatus } from "@/lib/types";

const CASE_STATUS: { value: PurchaseCaseStatus; label: string }[] = [
  { value: "exploring", label: "지역 탐색" }, { value: "reviewing", label: "후보 검토" },
  { value: "negotiating", label: "협상" }, { value: "decided", label: "결정" },
  { value: "archived", label: "보관" },
];
const PROPERTY_STATUS: { value: CaseProperty["status"]; label: string }[] = [
  { value: "reviewing", label: "검토 중" }, { value: "shortlisted", label: "우선 후보" },
  { value: "rejected", label: "제외" }, { value: "selected", label: "최종 선택" },
];
const ANALYSIS_LABEL = { appraisal: "시세", simulation: "자금", rights: "권리" } as const;

function won(value: number | null | undefined): string {
  return value == null ? "미입력" : `${Math.round(value / 10_000).toLocaleString()}만원`;
}
function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function textValue(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}
function analysisSummary(analysis: CandidateAnalysis): string {
  const summary = analysis.summary;
  if (analysis.analysis_type === "appraisal") {
    const verdict = textValue(summary.valuation_verdict);
    return `${won(numberValue(summary.estimated_value))}${verdict ? ` · ${verdict}` : ""}`;
  }
  if (analysis.analysis_type === "simulation") {
    const loan = numberValue(summary.loan_amount);
    const rate = numberValue(summary.annual_interest_rate);
    return `${loan == null ? "대출금 미확인" : `대출 ${won(loan)}`}${rate == null ? "" : ` · 금리 ${rate}%`}`;
  }
  const label = textValue(summary.risk_label) ?? textValue(summary.risk_grade) ?? "분석 완료";
  const score = numberValue(summary.risk_score);
  return `${label}${score == null ? "" : ` · 위험점수 ${score}`}`;
}

export default function CaseDetailPage() {
  const caseId = Number(useParams<{ id: string }>().id);
  const [item, setItem] = useState<PurchaseCase | null>(null);
  const [histories, setHistories] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [price, setPrice] = useState("");
  const [area, setArea] = useState("");
  const [historyId, setHistoryId] = useState("");
  const [error, setError] = useState("");
  const load = async () => setItem(await api.caseOne(caseId));

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.caseOne(caseId), api.history(100, 0, "")])
      .then(([caseResult, historyResult]) => {
        if (!cancelled) { setItem(caseResult); setHistories(historyResult.items as HistoryItem[]); }
      })
      .catch(() => { if (!cancelled) setError("매수 검토 케이스를 불러오지 못했습니다."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [caseId]);

  const addProperty = async (event: React.FormEvent) => {
    event.preventDefault(); setError("");
    try {
      await api.addCaseProperty(caseId, {
        name: name.trim(), address: address.trim(),
        asking_price: price ? Number(price) * 10_000 : undefined,
        area_sqm: area ? Number(area) : undefined,
        history_id: historyId ? Number(historyId) : undefined,
        source: historyId ? "appraisal" : "manual",
      });
      setName(""); setAddress(""); setPrice(""); setArea(""); setHistoryId(""); setFormOpen(false);
      await load();
    } catch { setError("후보를 추가하지 못했습니다. 입력값과 연결할 시세추정 이력을 확인해주세요."); }
  };

  if (loading) return <div className="py-20 text-center text-slate-400">불러오는 중...</div>;
  if (!item) return <div className="py-20 text-center text-slate-500">케이스를 찾을 수 없습니다.</div>;
  const properties = item.properties ?? [];

  return <div className="mx-auto max-w-6xl space-y-5">
    <Link href="/cases" className="text-sm font-medium text-primary hover:underline">← 매수 검토 목록</Link>
    <header className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
      <div><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">Purchase workspace</p><h1 className="text-2xl font-bold text-slate-900">{item.title}</h1><p className="mt-1 text-sm text-slate-500">{item.target_regions.join(", ") || "선호 지역 미정"} · 최대 예산 {won(item.budget_max)}</p></div>
      <select value={item.status} onChange={async (event) => { await api.updateCase(caseId, { status: event.target.value as PurchaseCaseStatus }); await load(); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">{CASE_STATUS.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}</select>
    </header>

    <section className="rounded-2xl border border-emerald-100 bg-emerald-50 p-5">
      <div className="flex items-center justify-between text-sm"><strong>전체 검토 진행률</strong><strong className="text-primary">{item.workspace?.progress_percent ?? 0}%</strong></div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white"><div className="h-full rounded-full bg-primary" style={{ width: `${item.workspace?.progress_percent ?? 0}%` }} /></div>
      <div className="mt-3 flex gap-4 text-xs text-slate-600"><span>완료 {item.workspace?.checklist_done ?? 0}/{item.workspace?.checklist_total ?? 0}</span><span className="text-amber-700">주의 {item.workspace?.warning_count ?? 0}</span><span className="text-red-700">진행 불가 {item.workspace?.blocked_count ?? 0}</span></div>
    </section>

    {(item.regions?.length ?? 0) > 0 && <section className="rounded-2xl border bg-white p-5 shadow-sm"><h2 className="font-bold">관심 지역</h2><div className="mt-3 grid gap-3 md:grid-cols-2">{item.regions?.map((region) => <article key={region.id} className="flex justify-between rounded-xl border p-4"><div><h3 className="flex items-center gap-2 text-sm font-semibold"><MapPinned size={15} className="text-primary" />{region.region_name}</h3><p className="mt-1 text-xs text-slate-500">중앙 거래가격 {won(region.stats_snapshot.median_price * 10_000)} · 표본 {region.stats_snapshot.sample_size.toLocaleString()}건</p></div><button onClick={async () => { await api.deleteCaseRegion(caseId, region.id); await load(); }} aria-label="관심 지역 삭제" className="text-slate-300 hover:text-red-500"><Trash2 size={15} /></button></article>)}</div></section>}

    <section className="rounded-2xl border bg-white shadow-sm">
      <div className="flex items-center justify-between border-b p-5"><div><h2 className="font-bold">후보 매물</h2><p className="mt-1 text-xs text-slate-500">분석 결과와 남은 검토 항목을 후보별로 관리합니다.</p></div><button onClick={() => setFormOpen((value) => !value)} className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white"><Plus size={15} className="mr-1 inline" />후보 추가</button></div>
      {formOpen && <form onSubmit={addProperty} className="grid gap-3 border-b bg-slate-50 p-5 md:grid-cols-2">
        <input required value={name} onChange={(event) => setName(event.target.value)} placeholder="후보명 또는 건물명" className="rounded-lg border px-3 py-2 text-sm" /><input value={address} onChange={(event) => setAddress(event.target.value)} placeholder="주소" className="rounded-lg border px-3 py-2 text-sm" />
        <input type="number" min="0" value={price} onChange={(event) => setPrice(event.target.value)} placeholder="매도 희망가(만원)" className="rounded-lg border px-3 py-2 text-sm" /><input type="number" min="0" step="0.01" value={area} onChange={(event) => setArea(event.target.value)} placeholder="면적(㎡)" className="rounded-lg border px-3 py-2 text-sm" />
        <select value={historyId} onChange={(event) => setHistoryId(event.target.value)} className="rounded-lg border px-3 py-2 text-sm md:col-span-2"><option value="">시세추정 이력 연결 안 함</option>{histories.map((history) => <option key={history.id} value={history.id}>#{history.id} {history.query} · {won(history.estimated_value)}</option>)}</select><button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white md:col-span-2">후보 저장</button>
      </form>}
      {error && <p className="m-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</p>}
      {properties.length === 0 ? <div className="py-16 text-center text-sm text-slate-400">검토할 부동산을 후보로 추가해보세요.</div> : <div className="space-y-4 p-4">{properties.map((property) => <CandidateCard key={property.id} property={property} caseId={caseId} reload={load} />)}</div>}
    </section>
  </div>;
}

function CandidateCard({ property, caseId, reload }: { property: CaseProperty; caseId: number; reload: () => Promise<void> }) {
  const analyses = new Map(property.analyses.map((analysis) => [analysis.analysis_type, analysis]));
  return <article className={`rounded-xl border p-5 ${property.status === "rejected" ? "bg-slate-50 opacity-70" : "bg-white"}`}>
    <div className="flex flex-col justify-between gap-3 md:flex-row"><div><div className="flex items-center gap-2"><h3 className="font-bold">{property.name}</h3><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">검토 {property.review_progress}%</span></div><p className="mt-1 text-sm text-slate-500">{property.address || "주소 미입력"}{property.area_sqm ? ` · ${property.area_sqm}㎡` : ""} · 희망가 {won(property.asking_price)}</p></div><div className="flex gap-2"><select value={property.status} onChange={async (event) => { await api.updateCaseProperty(caseId, property.id, { status: event.target.value as CaseProperty["status"] }); await reload(); }} className="rounded-lg border px-2 py-1 text-xs">{PROPERTY_STATUS.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}</select><button onClick={async () => { await api.deleteCaseProperty(caseId, property.id); await reload(); }} aria-label="후보 삭제" className="text-slate-300 hover:text-red-500"><Trash2 size={16} /></button></div></div>
    <div className="mt-4 grid gap-2 md:grid-cols-3">{(["appraisal", "simulation", "rights"] as const).map((type) => {
      const analysis = analyses.get(type);
      const href = type === "appraisal" ? `/appraisal?caseId=${caseId}&candidateId=${property.id}` : `/${type}`;
      const prepare = () => { if (type === "simulation") setSessionValue("simFromListing", JSON.stringify({ asking_price: property.asking_price, property_type: property.category, case_id: caseId, candidate_id: property.id })); if (type === "rights") setSessionValue("rightsCandidate", JSON.stringify({ market_price: property.appraisal?.estimated_value ?? property.asking_price, address: property.address, case_id: caseId, candidate_id: property.id })); };
      const warning = type === "rights" && analysis && textValue(analysis.summary.risk_grade) !== "safe";
      return <Link key={type} href={href} onClick={prepare} className={`rounded-lg border p-3 text-xs hover:border-emerald-300 ${warning ? "border-amber-200 bg-amber-50" : ""}`}><div className="flex justify-between"><strong>{ANALYSIS_LABEL[type]} 분석</strong>{analysis ? <CheckCircle2 size={15} className={warning ? "text-amber-600" : "text-emerald-600"} /> : <Circle size={15} className="text-slate-300" />}</div><p className="mt-1 truncate text-slate-500">{analysis ? analysisSummary(analysis) : type === "rights" ? "서류 업로드 필요" : type === "simulation" ? "금융 조건 입력 필요" : "분석 필요"}</p></Link>;
    })}</div>
    <div className="mt-4 flex flex-wrap gap-2">{property.checklist.map((check) => <button key={check.id} title={check.evidence || undefined} onClick={async () => { await api.updateCandidateChecklist(caseId, property.id, check.id, { status: check.status === "done" ? "todo" : "done" }); await reload(); }} className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs ${check.status === "done" ? "bg-emerald-100 text-emerald-700" : check.status === "warning" ? "bg-amber-100 text-amber-700" : check.status === "blocked" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-500"}`}>{check.status === "done" ? <CheckCircle2 size={12} /> : check.status === "warning" || check.status === "blocked" ? <AlertTriangle size={12} /> : <Circle size={12} />}{check.title}</button>)}</div>
    {property.history_id && <Link href={`/report/${property.history_id}`} className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"><FileSearch size={14} />시세추정 리포트 보기</Link>}
  </article>;
}
