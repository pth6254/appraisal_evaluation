"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

const EXAMPLES = [
  { label: "아파트", text: "마포구 아파트 84㎡ 매매", building: "마포래미안푸르지오" },
  { label: "오피스텔", text: "강남구 역삼동 오피스텔 33㎡", building: "" },
  { label: "상가", text: "서초구 상가 50평 매매", building: "" },
  { label: "오피스", text: "판교 사무실 100평 매매", building: "파르나스타워" },
  { label: "토지", text: "양평군 토지 500평 매매", building: "" },
];

type KakaoDoc = { place_name?: string; address_name?: string; category_group_code?: string; road_address_name?: string };

export default function AppraisalPage() {
  const router = useRouter();
  const [userInput, setUserInput]     = useState("");
  const [buildingName, setBuildingName] = useState("");
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KakaoDoc[]>([]);
  const [searching, setSearching]     = useState(false);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const result = await api.addressSearch(searchQuery, "keyword") as { documents: KakaoDoc[] };
      setSearchResults(result.documents || []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const selectAddress = (doc: KakaoDoc) => {
    const addr = doc.road_address_name || doc.address_name || "";
    setUserInput(addr);
    if (doc.place_name) setBuildingName(doc.place_name);
    setSearchResults([]);
    setSearchQuery("");
  };

  const handleSubmit = async () => {
    if (!userInput.trim()) { setError("감정평가 요청을 입력해주세요."); return; }
    setError("");
    setLoading(true);
    try {
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

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">🏠 부동산 감정평가</h1>
      <p className="text-slate-500 mb-6 text-sm">주소나 물건 정보를 입력하면 AI가 시장가치를 분석합니다.</p>

      {/* Kakao 주소 검색 */}
      <section className="bg-white rounded-xl shadow p-5 mb-4">
        <h2 className="font-semibold mb-3 text-slate-700">주소 검색 (선택)</h2>
        <div className="flex gap-2">
          <input
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            placeholder="건물명 또는 주소 검색..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSearch()}
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-4 py-2 bg-slate-700 text-white rounded-lg text-sm hover:bg-slate-800 disabled:opacity-50"
          >
            {searching ? "검색 중..." : "검색"}
          </button>
        </div>
        {searchResults.length > 0 && (
          <ul className="mt-2 border border-slate-200 rounded-lg divide-y max-h-48 overflow-y-auto">
            {searchResults.map((doc, i) => (
              <li
                key={i}
                className="px-4 py-2.5 text-sm cursor-pointer hover:bg-blue-50"
                onClick={() => selectAddress(doc)}
              >
                <div className="font-medium">{doc.place_name || doc.address_name}</div>
                {doc.place_name && <div className="text-xs text-slate-400">{doc.road_address_name || doc.address_name}</div>}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 빠른 예시 */}
      <section className="bg-white rounded-xl shadow p-5 mb-4">
        <h2 className="font-semibold mb-3 text-slate-700">빠른 예시</h2>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map(ex => (
            <button
              key={ex.label}
              className="px-3 py-1.5 text-sm bg-blue-50 text-blue-700 rounded-full border border-blue-200 hover:bg-blue-100"
              onClick={() => { setUserInput(ex.text); setBuildingName(ex.building); }}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </section>

      {/* 입력 폼 */}
      <section className="bg-white rounded-xl shadow p-5 mb-4">
        <h2 className="font-semibold mb-3 text-slate-700">감정평가 요청</h2>
        <div className="mb-3">
          <label className="block text-sm font-medium text-slate-600 mb-1">물건 정보 *</label>
          <textarea
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
            rows={3}
            placeholder="예: 마포구 아파트 84㎡ 매매, 강남구 역삼동 상가 50평..."
            value={userInput}
            onChange={e => setUserInput(e.target.value)}
          />
        </div>
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-600 mb-1">건물명 / 단지명 (선택)</label>
          <input
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            placeholder="예: 마포래미안푸르지오, 파르나스타워..."
            value={buildingName}
            onChange={e => setBuildingName(e.target.value)}
          />
        </div>

        {error && <p className="text-red-500 text-sm mb-3">⚠️ {error}</p>}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "AI 감정평가 실행 중... (30초~2분 소요)" : "🔍 감정평가 시작"}
        </button>
      </section>

      {loading && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700">
          <div className="font-semibold mb-1">분석 중입니다...</div>
          <div className="text-blue-500">LLM 에이전트가 실거래가·입지·수익성을 분석하고 있습니다.</div>
        </div>
      )}
    </div>
  );
}
