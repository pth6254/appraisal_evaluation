"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Bot, Database, MapPin, MessageCircle, Send, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ConciergeRegionItem, ConciergeResponse, PurchaseCase } from "@/lib/types";

type Message = {
  role: "user" | "assistant";
  content: string;
  response?: ConciergeResponse;
};

const HIDDEN_PATHS = [
  "/login", "/register", "/forgot-password", "/reset-password", "/privacy", "/terms",
];

const SUGGESTIONS = [
  "서울에서 10억 이하 아파트 동네 추천해줘",
  "실거주할 동네를 찾고 있어",
  "어떤 부동산 기능을 도와줄 수 있어?",
];

const formatPrice = (manwon: number) => manwon >= 10_000
  ? `${(manwon / 10_000).toFixed(manwon % 10_000 ? 1 : 0)}억원`
  : `${manwon.toLocaleString()}만원`;

const formatYm = (ym: string) => ym.length === 6 ? `${ym.slice(0, 4)}.${ym.slice(4)}` : ym;

function CriteriaChips({ response }: { response: ConciergeResponse }) {
  const criteria = response.criteria;
  const chips = [
    criteria.region_name,
    criteria.property_type === "apartment" ? "아파트" : criteria.property_type,
    criteria.budget_max_won ? `${(criteria.budget_max_won / 100_000_000).toLocaleString()}억원 이하` : null,
    criteria.area_min_sqm ? `${criteria.area_min_sqm}㎡ 이상` : null,
  ].filter((value): value is string => Boolean(value));
  if (!chips.length) return null;
  return <div className="mt-2 flex flex-wrap gap-1.5">{chips.map((chip) => (
    <span key={chip} className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-700">{chip}</span>
  ))}</div>;
}

function RegionCards({ response, saved, onSave }: {
  response: ConciergeResponse;
  saved: Set<string>;
  onSave: (response: ConciergeResponse, item: ConciergeRegionItem) => void;
}) {
  const items = response.data.items ?? [];
  if (!items.length) return null;
  return (
    <div className="mt-3 space-y-2">
      {items.slice(0, 5).map((item) => {
        const budgetFit = item.deal_count
          ? Math.round(item.budget_fit_count / item.deal_count * 100)
          : 0;
        return (
          <article key={item.region_code} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-1.5 text-sm font-bold text-slate-800">
                  <MapPin size={13} className="text-primary" />{item.region_name}
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  거래 {item.deal_count.toLocaleString()}건 · 대상 {item.asset_count.toLocaleString()}개
                </p>
              </div>
              <div className="shrink-0 text-right">
                <strong className="text-sm text-primary">{formatPrice(item.avg_price)}</strong>
                <p className="text-[10px] text-slate-400">평균 실거래가</p>
              </div>
            </div>
            <div className="mt-2 flex justify-between border-t border-slate-100 pt-2 text-[11px] text-slate-500">
              <span>{formatPrice(item.price_q1)}~{formatPrice(item.price_q3)}</span>
              {response.criteria.budget_max_won && <span className="font-semibold text-emerald-700">예산 내 {budgetFit}%</span>}
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px]"><span className="text-slate-400">중앙 {formatPrice(item.median_price)} · 신뢰도 {{ high: "높음", medium: "보통", low: "낮음" }[item.confidence]}</span><button type="button" disabled={saved.has(item.region_code)} onClick={() => onSave(response, item)} className="rounded-lg border border-emerald-200 px-2 py-1 font-semibold text-primary hover:bg-emerald-50 disabled:bg-emerald-50">{saved.has(item.region_code) ? "저장됨" : "케이스 저장"}</button></div>
          </article>
        );
      })}
      {response.data.period && (
        <p className="flex items-center gap-1 text-[10px] text-slate-400">
          <Database size={11} />국토교통부 실거래가 · {formatYm(response.data.period.from)}~{formatYm(response.data.period.to)}
        </p>
      )}
    </div>
  );
}

export default function ConciergeWidget() {
  const path = usePathname();
  const { user, loading: authLoading } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [cases, setCases] = useState<PurchaseCase[]>([]);
  const [caseId, setCaseId] = useState("");
  const [savedRegions, setSavedRegions] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api.cases().then((result) => {
      if (cancelled) return;
      setCases(result.items);
      if (result.items[0]) setCaseId(String(result.items[0].id));
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [user]);

  const saveRegion = async (response: ConciergeResponse, item: ConciergeRegionItem) => {
    try {
      let targetCaseId = caseId;
      if (!targetCaseId) {
        const created = await api.createCase({
          title: `${item.region_name} 매수 검토`,
          budget_max: response.criteria.budget_max_won ?? undefined,
        });
        targetCaseId = String(created.id);
        setCases([created]);
        setCaseId(targetCaseId);
      }
      await api.addCaseRegion(Number(targetCaseId), {
        region_code: item.region_code,
        property_type: response.criteria.property_type ?? "all",
        budget_max_won: response.criteria.budget_max_won ?? undefined,
        months: 12,
        source: "concierge",
      });
      setSavedRegions((current) => new Set(current).add(item.region_code));
    } catch {
      setMessages((current) => [...current, {
        role: "assistant", content: "관심 지역을 검토 케이스에 저장하지 못했습니다.",
      }]);
    }
  };

  const send = async (suggestion?: string) => {
    const message = (suggestion ?? input).trim();
    if (!message || sending) return;
    setInput("");
    setMessages((current) => [...current, { role: "user", content: message }]);
    setSending(true);
    try {
      const response = await api.conciergeMessage(message, conversationId);
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, {
        role: "assistant", content: response.answer, response,
      }]);
    } catch {
      setMessages((current) => [...current, {
        role: "assistant",
        content: "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      }]);
    } finally {
      setSending(false);
    }
  };

  if (authLoading || !user || HIDDEN_PATHS.some((hidden) => path.startsWith(hidden))) return null;

  return (
    <div className="no-print">
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="AI 컨시어지 열기"
          className="fixed bottom-5 right-4 z-40 flex items-center gap-2 rounded-full bg-brand px-4 py-3 text-sm font-bold text-white shadow-[0_12px_35px_rgba(14,36,30,0.3)] transition hover:-translate-y-0.5 hover:bg-brand-ink md:bottom-6 md:right-6"
        >
          <MessageCircle size={20} /><span>AI 컨시어지</span>
        </button>
      )}

      {open && (
        <>
          <button type="button" aria-label="AI 컨시어지 닫기" onClick={() => setOpen(false)} className="fixed inset-0 z-[65] bg-black/30 md:hidden" />
          <section
            role="dialog"
            aria-modal="true"
            aria-label="AI 부동산 컨시어지"
            className="fixed inset-0 z-[70] flex flex-col overflow-hidden bg-slate-50 shadow-2xl md:inset-auto md:bottom-6 md:right-6 md:h-[min(720px,calc(100vh-48px))] md:w-[430px] md:rounded-2xl md:border md:border-slate-200"
          >
            <header className="flex items-center justify-between bg-brand px-4 py-3.5 text-white">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/10"><Bot size={20} /></span>
                <div><h2 className="text-sm font-bold">AI 부동산 컨시어지</h2><p className="text-[11px] text-white/55">실거래 데이터와 서비스 기능을 연결합니다</p></div>
              </div>
              <button type="button" onClick={() => setOpen(false)} aria-label="닫기" className="rounded-lg p-2 text-white/70 hover:bg-white/10 hover:text-white"><X size={19} /></button>
            </header>

            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {messages.length === 0 && (
                <div className="pt-4 text-center">
                  <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-emerald-50 text-primary"><Sparkles size={22} /></span>
                  <h3 className="mt-3 text-base font-bold text-slate-800">어떤 부동산을 찾고 계세요?</h3>
                  <p className="mx-auto mt-1 max-w-[310px] text-xs leading-5 text-slate-500">현재는 실거래 기반 동네 추천을 지원하며, 매물 선택·가격 추정·세금 기능으로 확장됩니다.</p>
                  <div className="mt-5 space-y-2 text-left">{SUGGESTIONS.map((suggestion) => (
                    <button key={suggestion} type="button" onClick={() => send(suggestion)} className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-left text-xs text-slate-600 shadow-sm hover:border-emerald-300 hover:text-primary">{suggestion}</button>
                  ))}</div>
                </div>
              )}

              {messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[90%] rounded-2xl px-3.5 py-3 text-sm leading-6 ${message.role === "user" ? "rounded-br-md bg-primary text-white" : "rounded-bl-md bg-white text-slate-700 shadow-sm"}`}>
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.response && <CriteriaChips response={message.response} />}
                    {message.response && <RegionCards response={message.response} saved={savedRegions} onSave={saveRegion} />}
                  </div>
                </div>
              ))}
              {sending && <div className="flex justify-start"><div className="rounded-2xl rounded-bl-md bg-white px-4 py-3 text-xs text-slate-400 shadow-sm"><span className="animate-pulse">데이터를 확인하고 있어요…</span></div></div>}
              <div ref={bottomRef} />
            </div>

            <footer className="border-t border-slate-200 bg-white p-3">
              {cases.length > 0 && <div className="mb-2 flex items-center gap-2 px-1"><label className="shrink-0 text-[11px] text-slate-500">저장할 케이스</label><select value={caseId} onChange={(event) => setCaseId(event.target.value)} className="min-w-0 flex-1 rounded border border-slate-200 bg-slate-50 px-2 py-1 text-[11px]">{cases.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div>}
              <div className="flex items-end gap-2 rounded-xl border border-slate-300 bg-white p-1.5 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/10">
                <textarea
                  rows={1}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                      event.preventDefault(); send();
                    }
                  }}
                  placeholder="예산과 희망 지역을 말씀해 주세요"
                  disabled={sending}
                  className="max-h-28 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-slate-400"
                />
                <button type="button" onClick={() => send()} disabled={sending || !input.trim()} aria-label="메시지 보내기" className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-primary text-white hover:bg-primary-strong disabled:opacity-35"><Send size={17} /></button>
              </div>
              <p className="mt-2 text-center text-[10px] text-slate-400">실거래 기반 참고용 정보이며 전문 감정평가·법률·세무 자문이 아닙니다.</p>
            </footer>
          </section>
        </>
      )}
    </div>
  );
}
