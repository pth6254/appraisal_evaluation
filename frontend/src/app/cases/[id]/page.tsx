"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Calculator, FileSearch, MapPinned, Plus, Scale, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { HistoryItem, PurchaseCase, PurchaseCaseStatus } from "@/lib/types";

const STATUS: { value: PurchaseCaseStatus; label: string }[] = [
  { value: "exploring", label: "지역 탐색" }, { value: "reviewing", label: "후보 검토" },
  { value: "negotiating", label: "협상" }, { value: "decided", label: "결정" },
  { value: "archived", label: "보관" },
];

const won = (value: number | null | undefined) => value !== null && value !== undefined
  ? `${Math.round(value / 10_000).toLocaleString()}만원` : "미입력";

export default function CaseDetailPage() {
  const params = useParams<{ id: string }>();
  const caseId = Number(params.id);
  const [item, setItem] = useState<PurchaseCase | null>(null);
  const [histories, setHistories] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
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
        if (cancelled) return;
        setItem(caseResult);
        setHistories(historyResult.items as HistoryItem[]);
      })
      .catch(() => { if (!cancelled) setError("검토 케이스를 불러오지 못했습니다."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [caseId]);

  const changeStatus = async (status: PurchaseCaseStatus) => {
    const updated = await api.updateCase(caseId, { status });
    setItem((current) => current ? { ...current, status: updated.status } : current);
  };

  const addProperty = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api.addCaseProperty(caseId, {
        name: name.trim(), address: address.trim(),
        asking_price: price ? Number(price) * 10_000 : undefined,
        area_sqm: area ? Number(area) : undefined,
        history_id: historyId ? Number(historyId) : undefined,
        source: historyId ? "appraisal" : "manual",
      });
      setName(""); setAddress(""); setPrice(""); setArea(""); setHistoryId(""); setOpen(false);
      await load();
    } catch {
      setError("후보를 추가하지 못했습니다. 입력값과 시세추정 이력을 확인해주세요.");
    }
  };

  const removeProperty = async (propertyId: number) => {
    await api.deleteCaseProperty(caseId, propertyId);
    await load();
  };

  const removeRegion = async (regionId: number) => {
    await api.deleteCaseRegion(caseId, regionId);
    await load();
  };

  if (loading) return <div className="py-20 text-center text-slate-400">불러오는 중...</div>;
  if (!item) return <div className="py-20 text-center text-slate-500">케이스를 찾을 수 없습니다.</div>;

  const properties = item.properties ?? [];
  const caseRegions = item.regions ?? [];
  return (
    <div className="mx-auto max-w-6xl">
      <Link href="/cases" className="text-sm font-medium text-primary hover:underline">← 케이스 목록</Link>
      <div className="mt-4 flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{item.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{item.target_regions.join(", ") || "선호 지역 미정"} · 최대 예산 {won(item.budget_max)}</p>
        </div>
        <select value={item.status} onChange={(e) => changeStatus(e.target.value as PurchaseCaseStatus)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          {STATUS.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
        </select>
      </div>

      <div className="my-6 grid gap-3 md:grid-cols-4">
        <Link href="/recommendation" className="flex items-center gap-3 rounded-xl border bg-white p-4 text-sm font-semibold hover:border-emerald-300"><Plus size={18} className="text-primary" /> 후보 찾기</Link>
        <Link href="/appraisal" className="flex items-center gap-3 rounded-xl border bg-white p-4 text-sm font-semibold hover:border-emerald-300"><FileSearch size={18} className="text-primary" /> 시세추정</Link>
        <Link href="/simulation" className="flex items-center gap-3 rounded-xl border bg-white p-4 text-sm font-semibold hover:border-emerald-300"><Calculator size={18} className="text-primary" /> 자금 시뮬레이션</Link>
        <Link href="/rights" className="flex items-center gap-3 rounded-xl border bg-white p-4 text-sm font-semibold hover:border-emerald-300"><Scale size={18} className="text-primary" /> 권리 점검</Link>
      </div>

      <section className="mb-5 rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-5"><h2 className="font-bold text-slate-900">관심 지역</h2><p className="mt-0.5 text-xs text-slate-500">저장 당시의 실거래 통계와 조건을 보존합니다.</p></div>
        {caseRegions.length === 0 ? <div className="py-10 text-center text-sm text-slate-400">동네 탐색에서 관심 지역을 추가해 보세요.</div> : <div className="grid gap-3 p-4 md:grid-cols-2">{caseRegions.map((region) => {
          const stats = region.stats_snapshot;
          const confidence = { high: "높음", medium: "보통", low: "낮음" }[stats.confidence];
          return <article key={region.id} className="rounded-xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="flex items-center gap-1.5 text-sm font-bold text-slate-800"><MapPinned size={15} className="text-primary" />{region.region_name}</h3><p className="mt-1 text-xs text-slate-400">{region.period_from && region.period_to ? `${region.period_from}~${region.period_to}` : "집계 기간 없음"} · 표본 {stats.sample_size.toLocaleString()}건 · 신뢰도 {confidence}</p></div><button onClick={() => removeRegion(region.id)} aria-label="관심 지역 삭제" className="text-slate-300 hover:text-red-500"><Trash2 size={15} /></button></div><div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 text-xs"><div><span className="block text-slate-400">중앙 실거래가</span><strong>{won(stats.median_price * 10_000)}</strong></div><div><span className="block text-slate-400">가격 범위</span><strong>{won(stats.price_q1 * 10_000)}~{won(stats.price_q3 * 10_000)}</strong></div></div></article>;
        })}</div>}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 p-5">
          <div><h2 className="font-bold text-slate-900">후보 부동산</h2><p className="mt-0.5 text-xs text-slate-500">후보 {properties.length}개 · 시세추정 결과를 연결해 가격을 비교하세요.</p></div>
          <button onClick={() => setOpen((value) => !value)} className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white"><Plus size={15} className="mr-1 inline" />후보 추가</button>
        </div>

        {open && (
          <form onSubmit={addProperty} className="grid gap-3 border-b border-slate-100 bg-slate-50 p-5 md:grid-cols-2">
            <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="후보명/건물명" className="rounded-lg border px-3 py-2 text-sm" />
            <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="주소" className="rounded-lg border px-3 py-2 text-sm" />
            <input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="매도 희망가(만원)" className="rounded-lg border px-3 py-2 text-sm" />
            <input type="number" min="0" step="0.01" value={area} onChange={(e) => setArea(e.target.value)} placeholder="면적(㎡)" className="rounded-lg border px-3 py-2 text-sm" />
            <select value={historyId} onChange={(e) => setHistoryId(e.target.value)} className="rounded-lg border px-3 py-2 text-sm md:col-span-2">
              <option value="">시세추정 이력 연결 안 함</option>
              {histories.map((history) => <option key={history.id} value={history.id}>#{history.id} {history.query} · {won(history.estimated_value)}</option>)}
            </select>
            <button className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white md:col-span-2">후보 저장</button>
          </form>
        )}
        {error && <p className="m-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</p>}

        {properties.length === 0 ? <div className="py-16 text-center text-sm text-slate-400">추천 결과나 직접 찾은 부동산을 후보로 추가해보세요.</div> : (
          <div className="divide-y divide-slate-100">
            {properties.map((property) => {
              const gap = property.asking_price && property.appraisal?.estimated_value
                ? property.asking_price - property.appraisal.estimated_value : null;
              return (
                <article key={property.id} className="grid gap-4 p-5 md:grid-cols-[1fr_auto_auto_auto] md:items-center">
                  <div><h3 className="font-semibold text-slate-900">{property.name}</h3><p className="mt-1 text-sm text-slate-500">{property.address || "주소 미입력"}{property.area_sqm ? ` · ${property.area_sqm}㎡` : ""}</p>{property.notes && <p className="mt-1 text-xs text-slate-400">{property.notes}</p>}</div>
                  <div className="text-sm"><span className="block text-xs text-slate-400">희망가</span><strong>{won(property.asking_price)}</strong></div>
                  <div className="text-sm"><span className="block text-xs text-slate-400">AI 추정가</span><strong>{won(property.appraisal?.estimated_value)}</strong>{gap !== null && <span className={`ml-2 text-xs ${gap > 0 ? "text-red-500" : "text-emerald-600"}`}>{gap > 0 ? "+" : ""}{won(gap)}</span>}</div>
                  <div className="flex items-center gap-3">{property.history_id && <Link href={`/report/${property.history_id}`} className="text-xs font-semibold text-primary hover:underline">리포트</Link>}<button onClick={() => removeProperty(property.id)} className="text-slate-300 hover:text-red-500" aria-label="후보 삭제"><Trash2 size={16} /></button></div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
