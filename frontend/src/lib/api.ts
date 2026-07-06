import type { RecommendationRequest, SimulationRequest } from "./types";

const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...init,
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  appraisal: (
    userInput: string,
    buildingName = "",
    saveHistory = true,
    appraisalDate = "",      // YYYYMMDD
    appraisalPurpose = "",   // 담보/경매/과세/매매/보상/임의
  ) =>
    req("/appraisal", {
      method: "POST",
      body: JSON.stringify({
        user_input:        userInput,
        building_name:     buildingName,
        save_history:      saveHistory,
        appraisal_date:    appraisalDate,
        appraisal_purpose: appraisalPurpose,
      }),
    }),

  /** 비동기 시세추정 작업 시작 → { job_id } */
  appraisalJobStart: (
    userInput: string,
    buildingName = "",
    saveHistory = true,
    appraisalDate = "",
    appraisalPurpose = "",
  ) =>
    req<{ job_id: string }>("/appraisal/jobs", {
      method: "POST",
      body: JSON.stringify({
        user_input:        userInput,
        building_name:     buildingName,
        save_history:      saveHistory,
        appraisal_date:    appraisalDate,
        appraisal_purpose: appraisalPurpose,
      }),
    }),

  /** 작업 상태 폴링 → { status, step, history_id?, result? } */
  appraisalJob: (jobId: string) =>
    req<{
      job_id: string;
      status: "queued" | "running" | "done" | "error";
      step: string;
      error: string;
      history_id?: number;
      result?: Record<string, unknown>;
    }>(`/appraisal/jobs/${jobId}`),

  recommendation: (params: RecommendationRequest) =>
    req("/recommendation", { method: "POST", body: JSON.stringify(params) }),

  /** 실거래 기반 단지 추천 (전국) — 금액 단위: 만원 */
  recommendComplexes: (params: {
    region: string;
    budget_min?: number;
    budget_max?: number;
    area_m2?: number;
    months?: number;
    limit?: number;
  }) =>
    req<{
      region: string;
      sample_count: number;
      complex_count: number;
      region_avg_per_sqm: number;
      results: {
        complex_name: string; dong: string; avg_price: number;
        avg_per_sqm: number; avg_area_m2: number; deal_count: number;
        build_year: number; last_deal_ym: string; score: number; reasons: string[];
      }[];
      report: string;
      error: string;
    }>("/recommendation/complexes", { method: "POST", body: JSON.stringify(params) }),

  simulation: (params: SimulationRequest) =>
    req("/simulation", { method: "POST", body: JSON.stringify(params) }),

  comparison: (listings: object[], recommendationResults?: object[]) =>
    req("/comparison", {
      method: "POST",
      body: JSON.stringify({ listings, recommendation_results: recommendationResults }),
    }),

  history: (limit = 20, offset = 0, keyword = "") =>
    req<{ total: number; items: object[] }>(
      `/history?limit=${limit}&offset=${offset}&keyword=${encodeURIComponent(keyword)}`
    ),

  historyOne: (id: number) => req(`/history/${id}`),

  deleteHistory: (id: number) => req(`/history/${id}`, { method: "DELETE" }),

  deleteAllHistory: () => req("/history", { method: "DELETE" }),

  addressSearch: (query: string, type: "keyword" | "address" = "keyword") =>
    req<{ documents: object[]; meta: object }>(
      `/address/search?query=${encodeURIComponent(query)}&type=${type}`
    ),
};
