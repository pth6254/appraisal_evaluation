"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const PROPERTY_TYPES = [
  { category: "주거용", detail: "아파트",     label: "아파트",          hasDong: true,  hasHo: true  },
  { category: "주거용", detail: "오피스텔",   label: "오피스텔",        hasDong: true,  hasHo: true  },
  { category: "주거용", detail: "연립다세대", label: "빌라 / 연립",     hasDong: false, hasHo: true  },
  { category: "주거용", detail: "단독다가구", label: "단독 / 다가구",   hasDong: false, hasHo: false },
  { category: "상업용", detail: "상가",       label: "상가",            hasDong: false, hasHo: true  },
  { category: "업무용", detail: "사무실",     label: "사무실 / 오피스", hasDong: false, hasHo: true  },
  { category: "산업용", detail: "공장",       label: "공장",            hasDong: false, hasHo: false },
  { category: "산업용", detail: "창고",       label: "창고",            hasDong: false, hasHo: false },
  { category: "토지",   detail: "토지",       label: "토지",            hasDong: false, hasHo: false },
] as const;

type PropertyType = (typeof PROPERTY_TYPES)[number];
type KakaoDoc = {
  place_name?: string;
  address_name?: string;
  road_address_name?: string;
};

const STEPS = ["물건 종류", "주소 입력", "상세 정보"];

export default function AppraisalPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);

  // step 1
  const [selectedType, setSelectedType] = useState<PropertyType | null>(null);

  // step 2
  const [searchQuery, setSearchQuery]     = useState("");
  const [searchResults, setSearchResults] = useState<KakaoDoc[]>([]);
  const [searching, setSearching]         = useState(false);
  const [selectedAddress, setSelectedAddress] = useState("");
  const [buildingName, setBuildingName]   = useState("");
  const [manualInput, setManualInput]     = useState(false);

  // step 3
  const [dongNo, setDongNo]             = useState("");
  const [hoNo, setHoNo]                 = useState("");
  const [transactionType, setTransactionType] = useState("매매");
  const [areaSqm, setAreaSqm]           = useState("");
  const [askingPrice, setAskingPrice]   = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  const handleAddressSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const result = await api.addressSearch(searchQuery) as { documents: KakaoDoc[] };
      setSearchResults(result.documents || []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const selectAddress = (doc: KakaoDoc) => {
    setSelectedAddress(doc.road_address_name || doc.address_name || "");
    if (doc.place_name) setBuildingName(doc.place_name);
    setSearchResults([]);
    setSearchQuery("");
    setStep(3);
  };

  const buildUserInput = () => {
    const parts: string[] = [];
    if (selectedType) parts.push(selectedType.detail);
    if (selectedAddress) parts.push(selectedAddress);
    if (buildingName) parts.push(buildingName);
    if (dongNo) parts.push(dongNo);
    if (hoNo)   parts.push(hoNo);
    if (areaSqm) parts.push(`${areaSqm}㎡`);
    parts.push(transactionType);
    if (askingPrice) parts.push(`${askingPrice}만원`);
    return parts.join(" ");
  };

  const handleSubmit = async () => {
    if (!selectedAddress) { setError("주소를 입력해주세요."); return; }
    setError("");
    setLoading(true);
    try {
      const userInput = buildUserInput();
      const result = await api.appraisal(userInput, buildingName);
      sessionStorage.setItem("appraisalResult", JSON.stringify(result));
      sessionStorage.setItem("appraisalQuery", userInput);
      router.push("/report");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "감정평가 실패");
    } finally {
      setLoading(false);
    }
  };

  const goBack = () => setStep(s => s - 1);

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">부동산 감정평가</h1>
      <p className="text-slate-500 mb-5 text-sm">물건 정보를 단계별로 입력하면 AI가 시장가치를 분석합니다.</p>

      {/* 스텝 인디케이터 */}
      <div className="flex items-center gap-1 mb-6">
        {STEPS.map((label, i) => {
          const s = i + 1;
          const active  = step === s;
          const done    = step > s;
          return (
            <div key={s} className="flex items-center gap-1 flex-1">
              <div className={`flex items-center gap-2 flex-1 py-2 px-3 rounded-lg text-sm transition-colors ${
                active ? "bg-blue-600 text-white font-semibold" :
                done   ? "bg-blue-100 text-blue-700" :
                         "bg-slate-100 text-slate-400"
              }`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  active ? "bg-white text-blue-600" :
                  done   ? "bg-blue-400 text-white" :
                           "bg-slate-300 text-slate-500"
                }`}>{s}</span>
                <span className="truncate">{label}</span>
              </div>
              {s < STEPS.length && (
                <div className={`w-3 h-0.5 shrink-0 ${done ? "bg-blue-400" : "bg-slate-200"}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* ── STEP 1 : 물건 종류 선택 ──────────────────── */}
      {step === 1 && (
        <section className="bg-white rounded-xl shadow p-6">
          <h2 className="font-semibold text-base text-slate-800 mb-4">어떤 종류의 부동산인가요?</h2>
          <div className="grid grid-cols-3 gap-3">
            {PROPERTY_TYPES.map(pt => (
              <button
                key={pt.detail}
                onClick={() => { setSelectedType(pt); setStep(2); }}
                className="p-4 rounded-xl border-2 border-slate-200 hover:border-blue-500 hover:bg-blue-50 text-left transition-colors group"
              >
                <div className="font-semibold text-sm text-slate-800 group-hover:text-blue-700">{pt.label}</div>
                <div className="text-xs text-slate-400 mt-0.5">{pt.category}</div>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* ── STEP 2 : 주소 입력 ───────────────────────── */}
      {step === 2 && (
        <section className="bg-white rounded-xl shadow p-6">
          <button onClick={goBack} className="text-sm text-slate-400 hover:text-slate-700 mb-4 flex items-center gap-1 transition-colors">
            ← 뒤로
          </button>

          <h2 className="font-semibold text-base text-slate-800 mb-1">
            {selectedType?.label} 주소를 검색해주세요
          </h2>
          <p className="text-xs text-slate-400 mb-4">건물명, 단지명, 도로명 주소로 검색하세요</p>

          <div className="flex gap-2 mb-3">
            <input
              className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="예: 래미안원베일리, 서초구 반포동..."
              value={searchQuery}
              onChange={e => { setSearchQuery(e.target.value); setManualInput(false); }}
              onKeyDown={e => e.key === "Enter" && handleAddressSearch()}
              autoFocus
            />
            <button
              onClick={handleAddressSearch}
              disabled={searching}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {searching ? "검색 중..." : "검색"}
            </button>
          </div>

          {/* 검색 결과 */}
          {searchResults.length > 0 && (
            <ul className="border border-slate-200 rounded-lg divide-y max-h-64 overflow-y-auto mb-4">
              {searchResults.map((doc, i) => (
                <li
                  key={i}
                  className="px-4 py-3 text-sm cursor-pointer hover:bg-blue-50 transition-colors"
                  onClick={() => selectAddress(doc)}
                >
                  <div className="font-medium text-slate-800">{doc.place_name || doc.address_name}</div>
                  {doc.place_name && (
                    <div className="text-xs text-slate-400 mt-0.5">{doc.road_address_name || doc.address_name}</div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* 선택된 주소 표시 */}
          {selectedAddress && !searchResults.length && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 flex items-center justify-between mb-4">
              <div>
                <div className="text-xs text-blue-500 font-medium mb-0.5">선택된 주소</div>
                <div className="text-sm font-medium text-slate-800">{selectedAddress}</div>
                {buildingName && <div className="text-xs text-slate-500">{buildingName}</div>}
              </div>
              <button
                onClick={() => { setSelectedAddress(""); setBuildingName(""); }}
                className="text-slate-400 hover:text-red-500 ml-3 transition-colors"
              >✕</button>
            </div>
          )}

          {/* 직접 입력 */}
          {!selectedAddress && (
            <div className="mt-3">
              {!manualInput ? (
                <button
                  onClick={() => setManualInput(true)}
                  className="text-xs text-blue-500 hover:underline"
                >
                  주소를 직접 입력하기
                </button>
              ) : (
                <input
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  placeholder="예: 서울시 서초구 반포동 1번지"
                  autoFocus
                  onChange={e => setSelectedAddress(e.target.value)}
                />
              )}
            </div>
          )}

          <button
            onClick={() => setStep(3)}
            disabled={!selectedAddress}
            className="mt-5 w-full py-2.5 bg-blue-600 text-white rounded-xl font-medium text-sm hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            다음 단계 →
          </button>
        </section>
      )}

      {/* ── STEP 3 : 상세 정보 ───────────────────────── */}
      {step === 3 && (
        <section className="bg-white rounded-xl shadow p-6">
          <button onClick={goBack} className="text-sm text-slate-400 hover:text-slate-700 mb-4 flex items-center gap-1 transition-colors">
            ← 뒤로
          </button>

          <h2 className="font-semibold text-base text-slate-800 mb-4">상세 정보 입력</h2>

          {/* 선택 요약 */}
          <div className="bg-slate-50 rounded-lg px-4 py-3 mb-5 text-sm flex flex-wrap gap-x-3 gap-y-1">
            <span><span className="text-slate-400">종류</span> <span className="font-medium text-slate-700">{selectedType?.label}</span></span>
            <span className="text-slate-300">|</span>
            <span><span className="text-slate-400">주소</span> <span className="font-medium text-slate-700">{selectedAddress}</span></span>
            {buildingName && (
              <>
                <span className="text-slate-300">|</span>
                <span className="font-medium text-slate-700">{buildingName}</span>
              </>
            )}
          </div>

          {/* 동 / 호수 */}
          {(selectedType?.hasDong || selectedType?.hasHo) && (
            <div className={`grid gap-3 mb-4 ${selectedType.hasDong ? "grid-cols-2" : "grid-cols-1"}`}>
              {selectedType.hasDong && (
                <div>
                  <label className="block text-sm font-medium text-slate-600 mb-1">
                    동 <span className="text-slate-400 font-normal text-xs">(선택)</span>
                  </label>
                  <input
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="예: 101동"
                    value={dongNo}
                    onChange={e => setDongNo(e.target.value)}
                  />
                </div>
              )}
              {selectedType.hasHo && (
                <div>
                  <label className="block text-sm font-medium text-slate-600 mb-1">
                    호수 <span className="text-slate-400 font-normal text-xs">(선택)</span>
                  </label>
                  <input
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                    placeholder="예: 201호"
                    value={hoNo}
                    onChange={e => setHoNo(e.target.value)}
                  />
                </div>
              )}
            </div>
          )}

          {/* 면적 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-600 mb-1">
              전용면적 <span className="text-slate-400 font-normal text-xs">(선택 · ㎡)</span>
            </label>
            <input
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="예: 84"
              type="number"
              min="1"
              value={areaSqm}
              onChange={e => setAreaSqm(e.target.value)}
            />
          </div>

          {/* 거래 유형 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-600 mb-2">거래 유형</label>
            <div className="flex gap-2">
              {["매매", "전세", "월세"].map(t => (
                <button
                  key={t}
                  onClick={() => setTransactionType(t)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    transactionType === t
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* 희망 가격 */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-600 mb-1">
              호가 / 희망 가격 <span className="text-slate-400 font-normal text-xs">(선택 · 만원)</span>
            </label>
            <input
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              placeholder="예: 150000"
              type="number"
              min="0"
              value={askingPrice}
              onChange={e => setAskingPrice(e.target.value)}
            />
          </div>

          {error && <p className="text-red-500 text-sm mb-3">⚠️ {error}</p>}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "AI 감정평가 실행 중... (30초~2분 소요)" : "감정평가 시작"}
          </button>
        </section>
      )}

      {loading && (
        <div className="mt-4 bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700">
          <div className="font-semibold mb-1">분석 중입니다...</div>
          <div className="text-blue-500">LLM 에이전트가 실거래가·입지·수익성을 분석하고 있습니다.</div>
        </div>
      )}
    </div>
  );
}
