"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Msg = {
  role: "user" | "assistant";
  content: string;
  sources?: { title: string; source: string }[];
  tool?: string | null;
};

const SUGGESTIONS = [
  "전세 보증금을 못 받고 있는데 어떻게 해야 하나요?",
  "성인 자녀에게 5억 증여하면 증여세 얼마인가요?",
  "묵시적 갱신되면 언제 나갈 수 있나요?",
  "1주택 10억에 팔면 양도세 나오나요?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (text?: string) => {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput("");
    const nextMsgs: Msg[] = [...messages, { role: "user", content: q }];
    setMessages(nextMsgs);
    setLoading(true);
    try {
      const history = nextMsgs.slice(0, -1).slice(-6).map(m => ({ role: m.role, content: m.content }));
      const res = await api.chat(q, history);
      setMessages([...nextMsgs, {
        role: "assistant", content: res.answer,
        sources: res.sources, tool: res.tool_used,
      }]);
    } catch (e: unknown) {
      setMessages([...nextMsgs, {
        role: "assistant",
        content: "죄송합니다. 답변 생성에 실패했습니다. 잠시 후 다시 시도해주세요."
          + (e instanceof Error ? ` (${e.message.slice(0, 80)})` : ""),
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-3rem)]">
      <h1 className="text-2xl font-bold mb-1">부동산 법률·세금 AI 안내</h1>
      <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-3 py-2 rounded-lg mb-4">
        일반 정보 안내 서비스입니다. 법률·세무 상담이 아니며, 개별 사안은 변호사·세무사와 상담하세요.
      </p>

      {/* 메시지 목록 */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="text-center pt-10">
            <p className="text-slate-400 text-sm mb-5">
              임대차·전세사기·세금·상속·증여 관련 질문을 해보세요.<br />
              증여세·상속세·양도세는 세법 기반 계산기가 자동 실행됩니다.
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => send(s)}
                  className="text-xs bg-white border border-slate-200 rounded-full px-3 py-1.5 text-slate-600 hover:border-primary hover:text-primary">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
              m.role === "user" ? "bg-primary text-white" : "bg-white shadow text-slate-800"
            }`}>
              {m.tool && (
                <span className="inline-block text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5 mb-2">
                  {m.tool} 실행됨
                </span>
              )}
              <div>{m.content}</div>
              {m.sources && m.sources.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-100">
                  <p className="text-[10px] text-slate-400 mb-1">참고 자료</p>
                  <div className="flex flex-wrap gap-1">
                    {m.sources.map((s, j) => (
                      <span key={j} className="text-[10px] bg-slate-50 border border-slate-200 rounded px-1.5 py-0.5 text-slate-500">
                        {s.title}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white shadow rounded-2xl px-4 py-3 text-sm text-slate-400 animate-pulse">
              답변 작성 중...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 입력 */}
      <div className="flex gap-2 pt-3 border-t border-slate-200">
        <input
          className="flex-1 border border-slate-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
          placeholder="질문을 입력하세요 (예: 전세 계약 전 뭘 확인해야 하나요?)"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.nativeEvent.isComposing && send()}
          disabled={loading}
        />
        <button onClick={() => send()} disabled={loading || !input.trim()}
          className="px-5 py-2.5 bg-primary text-white rounded-xl text-sm font-semibold hover:bg-primary-strong disabled:opacity-40">
          전송
        </button>
      </div>
    </div>
  );
}
