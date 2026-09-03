// Typed API client for the credit-scoring backend.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface ApiErrorShape {
  code: string;
  message: string;
  details?: { field: string; issue: string }[];
}

export class ApiError extends Error {
  code: string;
  status: number;
  details: { field: string; issue: string }[];

  constructor(shape: ApiErrorShape, status: number) {
    super(shape.message || "Request failed");
    this.code = shape.code;
    this.status = status;
    this.details = shape.details ?? [];
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // the token may live in localStorage (remember me) or sessionStorage
  const token = sessionToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { "X-Session-Token": token } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let shape: ApiErrorShape = {
      code: "unknown",
      message: `Request failed (${res.status})`,
    };
    try {
      const data = await res.json();
      if (data?.error) shape = data.error as ApiErrorShape;
    } catch {
      // non-JSON error body — keep the generic shape
    }
    throw new ApiError(shape, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};

/** Download the applicant's PDF report (blob download with session header). */
export async function downloadReport(applicationId: number): Promise<void> {
  const token = sessionToken();
  const res = await fetch(
    `${API_BASE}/api/applications/${applicationId}/report`,
    { headers: token ? { "X-Session-Token": token } : {} },
  );
  if (!res.ok) {
    let shape: ApiErrorShape = {
      code: "unknown",
      message: `Could not download the report (${res.status})`,
    };
    try {
      const data = await res.json();
      if (data?.error) shape = data.error as ApiErrorShape;
    } catch {
      // non-JSON error body — keep the generic shape
    }
    throw new ApiError(shape, res.status);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `repayment_assessment_app${applicationId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// ------------------------------------------------------------- session state

/** Notify listeners (e.g. the header) that the session changed. */
function announceSessionChange() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("ccs-session"));
  }
}

export function saveSession(token: string, name: string, remember = true) {
  // "Remember me": localStorage persists across browser restarts;
  // sessionStorage is cleared when the browser window closes
  const storage = remember ? localStorage : sessionStorage;
  const other = remember ? sessionStorage : localStorage;
  other.removeItem("ccs_session");
  other.removeItem("ccs_name");
  storage.setItem("ccs_session", token);
  storage.setItem("ccs_name", name);
  announceSessionChange();
}

function readSessionKey(key: string): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(key) ?? sessionStorage.getItem(key);
}

export function sessionToken(): string | null {
  return readSessionKey("ccs_session");
}

export function displayName(): string {
  return readSessionKey("ccs_name") ?? "";
}

export function clearSession() {
  localStorage.removeItem("ccs_session");
  localStorage.removeItem("ccs_name");
  localStorage.removeItem("ccs_app");
  sessionStorage.removeItem("ccs_session");
  sessionStorage.removeItem("ccs_name");
  announceSessionChange();
}

/** End the server-side session (best effort), then the caller clears locally. */
export async function logout(): Promise<void> {
  try {
    await api.post("/api/auth/logout");
  } catch {
    // token already invalid/expired — nothing to invalidate server-side
  }
}

export function currentAppId(): number | null {
  const value =
    typeof window === "undefined" ? null : localStorage.getItem("ccs_app");
  return value ? Number(value) : null;
}

export function setCurrentApp(id: number) {
  localStorage.setItem("ccs_app", String(id));
}

export function clearCurrentApp() {
  localStorage.removeItem("ccs_app");
}

// ------------------------------------------------------- password recovery

export interface ForgotPasswordResponse {
  message: string;
  dev_reset_url?: string | null;
  dev_notice?: string | null;
}

export async function requestPasswordReset(
  cnic: string,
): Promise<ForgotPasswordResponse> {
  return api.post<ForgotPasswordResponse>("/api/auth/forgot-password", {
    cnic,
  });
}

export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<{ message: string }> {
  return api.post<{ message: string }>("/api/auth/reset-password", {
    token,
    new_password: newPassword,
    confirm_password: newPassword,
  });
}

// ----------------------------------------------------------------- API types

export interface ApplicantPublic {
  id: number;
  full_name: string;
  cnic_masked: string;
  mobile_masked: string;
  email_masked: string;
  cnic_status: string;
}

export interface ApplicationSummary {
  id: number;
  status: string;
  occupation: string;
  requested_loan_size: number;
  repayment_score: number | null;
  score_category: string | null;
  created_at: string;
}

export interface RegisterResponse {
  session_token: string;
  applicant: ApplicantPublic;
  cnic_notice?: string | null;
}

export interface LoginResponse extends RegisterResponse {
  applications: ApplicationSummary[];
}

export interface VerificationPublic {
  status: string;
  provider: string;
  verified_at: string | null;
}

export interface ConsentPublic {
  wallet_activity: boolean;
  telecom_activity: boolean;
  digital_transactions: boolean;
  previous_loan_info: boolean;
  granted_at: string;
}

export interface QuestionnairePublic {
  psychometric_score: number;
  consistency_warnings: string[];
  completed_at: string;
}

export interface Contributor {
  feature: string;
  value: string;
  shap_value: number;
}

export interface Explanation {
  summary: string;
  positive_factors: string[];
  negative_factors: string[];
  overall_explanation: string;
  source: string;
}

export interface AssessmentDetailPublic {
  repayment_score: number;
  raw_score: number;
  score_category: string;
  explanation_source: string;
  base_value: number;
  positive_contributors: Contributor[];
  negative_contributors: Contributor[];
  all_contributions: Contributor[];
  explanation: Explanation;
  created_at: string;
}

export interface ApplicationDetail {
  id: number;
  status: string;
  occupation: string;
  requested_loan_size: number;
  repayment_score: number | null;
  score_category: string | null;
  created_at: string;
  age: number;
  monthly_income: number;
  monthly_debt_payments: number;
  existing_loan_history: string;
  digital_purchase_frequency: number;
  applicant: ApplicantPublic;
  verification: VerificationPublic | null;
  consent: ConsentPublic | null;
  questionnaire: QuestionnairePublic | null;
  assessment: AssessmentDetailPublic | null;
}

export interface Question {
  id: number;
  dimension: string;
  text: string;
}

export interface QuestionsResponse {
  scale: string[];
  note: string;
  questions: Question[];
}

export interface ConsentInfoResponse {
  categories: Record<string, string>;
  notice: string;
}

export interface OtpRequestResult {
  status: string;
  expires_in_seconds: number;
  notice: string;
  simulated_otp?: string;
}

export interface OtpVerifyResult {
  status: string;
  message?: string | null;
  attempts_remaining?: number | null;
  verified_at?: string | null;
  notice?: string | null;
}

export interface ConsentGrantResult {
  status: string;
  categories: string[];
  granted_at: string;
  notice: string;
}

export interface QuestionnaireSubmitResult {
  psychometric_score: number;
  consistency_warnings: string[];
  completed_at: string;
  note: string;
}

export interface ScoringResponse {
  application_id: number;
  status: string;
  repayment_score: number;
  raw_score: number;
  score_category: string;
  base_value: number;
  positive_contributors: Contributor[];
  negative_contributors: Contributor[];
  all_contributions: Contributor[];
  explanation: Explanation;
  explanation_source: string;
  consistency_warnings: string[];
  provider_note: string;
  disclaimer: string;
  report_filename: string;
}

// -------------------------------------------------------------------- helpers

export const OCCUPATIONS = [
  "Salaried",
  "Self-Employed",
  "Business Owner",
  "Freelancer",
  "Daily Wage Worker",
  "Other",
];

export const LOAN_HISTORY_OPTIONS = [
  "No Previous Loan",
  "Good Repayment History",
  "Delayed Repayment History",
  "Previous Default",
];

export const CATEGORY_COLORS: Record<string, string> = {
  "Very Low": "#b91c1c",
  Low: "#c2410c",
  Moderate: "#ca8a04",
  High: "#15803d",
  "Very High": "#14532d",
};

export function formatPKR(value: number): string {
  return `PKR ${value.toLocaleString("en-PK")}`;
}

export function formatDate(iso: string): string {
  // Backend timestamps are naive UTC — append Z when no offset is present
  // so browsers in other timezones don't shift the date by hours.
  const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  return new Date(normalized).toLocaleDateString("en-PK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Where an application should go next, given its current status. */
export function nextStepFor(status: string): string {
  switch (status) {
    case "created":
      return "/verify";
    case "verified":
      return "/consent";
    case "consented":
      return "/assessment";
    case "assessed":
      return "/processing";
    case "scored":
      return "/results";
    default:
      return "/dashboard";
  }
}
