// TypeScript types mirroring Pydantic schemas

export interface ComparableTransaction {
  complex_name?: string;
  address?: string;
  area_m2?: number;
  deal_price?: number;
  deal_date?: string;
  price_per_m2?: number;
  source?: string;
  match_level?: string;
}

export interface AppraisalResult {
  estimated_price?: number;
  low_price?: number;
  high_price?: number;
  asking_price?: number;
  gap_rate?: number;
  judgement: string;
  confidence: number;
  comparables: ComparableTransaction[];
  warnings: string[];
  data_source: string[];
  raw?: Record<string, unknown>;
}

export interface PropertyListing {
  listing_id: string;
  complex_name?: string;
  address: string;
  region?: string;
  property_type: string;
  area_m2?: number;
  asking_price: number;
  floor?: number;
  built_year?: number;
  lat?: number;
  lng?: number;
  station_distance_m?: number;
  school_distance_m?: number;
  deposit_price?: number;
  maintenance_fee?: number;
  description?: string;
}

export interface RecommendationResult {
  listing: PropertyListing;
  total_score: number;
  price_score?: number;
  location_score?: number;
  investment_score?: number;
  risk_score?: number;
  recommendation_label?: string;
  reasons?: string[];
  risks?: string[];
}

export interface AcquisitionCost {
  acquisition_tax: number;
  brokerage_fee: number;
  other_cost: number;
  total: number;
}

export interface LoanSummary {
  monthly_payment: number;
  total_repayment: number;
  total_interest: number;
}

export interface CashFlowSummary {
  monthly_rental_income: number;
  monthly_loan_payment: number;
  monthly_management_fee: number;
  monthly_net: number;
}

export interface ScenarioResult {
  annual_growth_rate: number;
  expected_sale_price: number;
  capital_gain: number;
  total_rental_income: number;
  net_profit: number;              // 세후
  equity_roi: number;
  annual_equity_roi: number;
  rental_yield: number;
  pre_tax_profit: number;
  capital_gains_tax: number;
  holding_tax_total: number;
  sale_brokerage_fee: number;
  cgt_note: string;
  infinite_leverage: boolean;
}

export interface FinanceCheck {
  ltv: number;
  ltv_limit: number;
  ltv_exceeded: boolean;
  ltv_max_loan: number;
  dsr?: number;
  dsr_limit: number;
  dsr_exceeded: boolean;
  stress_rate?: number;
  dsr_annual_payment?: number;
  dsr_max_loan?: number;
}

export interface RateSensitivityCell {
  growth_rate: number;
  interest_rate: number;
  annual_equity_roi: number;
  net_profit: number;
}

export interface SimulationResult {
  purchase_price: number;
  loan_amount: number;
  equity: number;
  required_cash: number;
  acquisition_cost: AcquisitionCost;
  loan: LoanSummary;
  cash_flow: CashFlowSummary;
  scenario_base: ScenarioResult;
  scenario_bull: ScenarioResult;
  scenario_bear: ScenarioResult;
  tax_rules_as_of: string;
  official_price_used: number;
  official_price_estimated: boolean;
  finance_check?: FinanceCheck;
  breakeven_growth_rate?: number;
  rate_sensitivity: RateSensitivityCell[];
}

export interface PropertyComparisonRow {
  rank: number;
  is_winner: boolean;
  listing: PropertyListing;
  total_score?: number;
  highlights?: string[];
  warnings?: string[];
  simulation_result?: SimulationResult;
}

export interface ComparisonResult {
  rows: PropertyComparisonRow[];
  decision_report?: string;
}

export interface HistoryItem {
  id: number;
  query: string;
  category: string;
  created: string;
  estimated_value?: number;
  valuation_verdict?: string;
  investment_grade?: string;
  cap_rate?: number;
}

// Request types
export interface RecommendationRequest {
  region?: string;
  property_type?: string;
  budget_min?: number;
  budget_max?: number;
  area_m2?: number;
  purpose?: string;
  limit?: number;
}

export interface SimulationRequest {
  purchase_price: number;
  loan_ratio: number;
  annual_interest_rate: number;
  loan_years: number;
  repayment_type: "equal_payment" | "equal_principal" | "interest_only";
  holding_years: number;
  expected_annual_growth_rate: number;
  rent_deposit?: number;
  rent_fee?: number;
  monthly_management_fee?: number;
  property_type: string;
  owned_homes: number;
  official_price?: number;
  residence_years?: number;
  vacancy_rate?: number;
  adjusted_area?: boolean;
  annual_income?: number;
  existing_loan_annual_payment?: number;
}
