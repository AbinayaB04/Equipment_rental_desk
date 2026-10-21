/**
 * Typed HTTP API client for the Equipment Rental Desk frontend.
 * Provides type-safe requests, structured error parsing, reviewer test-clock support,
 * and robust handling of 204 No Content and network errors.
 */

import type {
  ApiErrorResponse,
  HealthResponse,
  ItemCreate,
  ItemListParams,
  ItemResponse,
  ItemUpdate,
  LoanListParams,
  LoanReserveRequest,
  LoanResponse,
  MemberCreate,
  MemberListParams,
  MemberResponse,
  MemberStatementResponse,
  MemberUpdate,
  OverdueLoansParams,
  PaymentCreateRequest,
  PaymentResponse,
} from "./types.ts";
import { buildQueryString } from "./utils.ts";

// ============================================================================
// Base URL Resolution
// ============================================================================

function resolveEnvBaseUrl(): string | undefined {
  try {
    if (
      typeof import.meta !== "undefined" &&
      (import.meta as unknown as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL
    ) {
      return (import.meta as unknown as { env: { VITE_API_BASE_URL: string } }).env.VITE_API_BASE_URL;
    }
  } catch {
    // import.meta.env not available in non-Vite environments
  }

  try {
    const globalObj = typeof globalThis !== "undefined" ? (globalThis as Record<string, unknown>) : {};
    const proc = globalObj.process as { env?: Record<string, string | undefined> } | undefined;
    if (proc?.env?.VITE_API_BASE_URL) {
      return proc.env.VITE_API_BASE_URL;
    }
  } catch {
    // process.env not available in browser
  }

  return undefined;
}

const defaultRawBaseUrl = resolveEnvBaseUrl();

let configuredBaseUrl: string | undefined = defaultRawBaseUrl
  ? defaultRawBaseUrl.replace(/\/+$/, "")
  : undefined;

export const API_BASE_URL: string | undefined = configuredBaseUrl;

export function getBaseUrl(): string {
  if (!configuredBaseUrl) {
    throw new Error(
      "VITE_API_BASE_URL is not set. Copy .env.example to .env in the repository root.",
    );
  }
  return configuredBaseUrl;
}

export function setBaseUrl(url: string | undefined): void {
  configuredBaseUrl = url ? url.replace(/\/+$/, "") : undefined;
}

// ============================================================================
// Reviewer Test-Clock State
// ============================================================================

let globalTestClock: string | null = null;
let globalTestClockKey: string | null = null;

export function setGlobalTestClock(timestamp: string | Date | null): void {
  if (!timestamp) {
    globalTestClock = null;
    return;
  }
  globalTestClock = typeof timestamp === "string" ? timestamp : timestamp.toISOString();
}

export function getGlobalTestClock(): string | null {
  return globalTestClock;
}

export function setGlobalTestClockKey(key: string | null): void {
  globalTestClockKey = key;
}

// ============================================================================
// Typed Error Class
// ============================================================================

export class ApiClientError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly error: string;
  public readonly detail: string;
  public readonly requestId: string | null;

  constructor(status: number, data: ApiErrorResponse) {
    super(data.detail || data.error || `HTTP ${status}`);
    this.name = "ApiClientError";
    this.status = status;
    this.code = data.code || "HTTP_ERROR";
    this.error = data.error || "Error";
    this.detail = data.detail || this.message;
    this.requestId = data.request_id ?? null;
  }
}

// ============================================================================
// Core Request Helper
// ============================================================================

export interface RequestOptions {
  signal?: AbortSignal;
  testClock?: string | Date | null;
  testClockKey?: string | null;
  headers?: Record<string, string>;
}

async function request<T>(
  path: string,
  method: "GET" | "POST" | "PATCH" | "DELETE" = "GET",
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options?.headers ?? {}),
  };

  if (body !== undefined && body !== null) {
    headers["Content-Type"] = "application/json";
  }

  // Inject reviewer test clock if active (per-request or global)
  const activeClock = options?.testClock !== undefined ? options.testClock : globalTestClock;
  if (activeClock) {
    headers["X-Test-Clock"] =
      typeof activeClock === "string" ? activeClock : activeClock.toISOString();
  }

  const activeClockKey =
    options?.testClockKey !== undefined ? options.testClockKey : globalTestClockKey;
  if (activeClockKey) {
    headers["X-Test-Clock-Key"] = activeClockKey;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined && body !== null ? JSON.stringify(body) : undefined,
      signal: options?.signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    const message = error instanceof Error ? error.message : "Network request failed.";
    throw new ApiClientError(0, {
      error: "Network Error",
      detail: message,
      code: "NETWORK_ERROR",
      request_id: null,
    });
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  // Handle errors
  if (!response.ok) {
    let errorData: ApiErrorResponse;
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      try {
        errorData = (await response.json()) as ApiErrorResponse;
      } catch {
        errorData = {
          error: response.statusText || "HTTP Error",
          detail: `Request failed with HTTP status ${response.status}.`,
          code: "HTTP_ERROR",
          request_id: response.headers.get("x-request-id"),
        };
      }
    } else {
      const rawText = await response.text();
      errorData = {
        error: response.statusText || "HTTP Error",
        detail: rawText || `Request failed with HTTP status ${response.status}.`,
        code: "HTTP_ERROR",
        request_id: response.headers.get("x-request-id"),
      };
    }

    throw new ApiClientError(response.status, errorData);
  }

  // Parse JSON response body
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return undefined as unknown as T;
}

// ============================================================================
// Health
// ============================================================================

export async function fetchHealth(signal?: AbortSignal, options?: RequestOptions): Promise<HealthResponse> {
  return request<HealthResponse>("/health", "GET", undefined, { ...options, signal: signal ?? options?.signal });
}

// ============================================================================
// Items API
// ============================================================================

export async function fetchItems(
  params?: ItemListParams,
  options?: RequestOptions,
): Promise<ItemResponse[]> {
  const query = buildQueryString(
    params as Record<string, string | number | boolean | null | undefined>,
  );
  return request<ItemResponse[]>(`/items${query}`, "GET", undefined, options);
}

export async function getItem(
  itemId: number,
  options?: RequestOptions,
): Promise<ItemResponse> {
  return request<ItemResponse>(`/items/${itemId}`, "GET", undefined, options);
}

export async function createItem(
  payload: ItemCreate,
  options?: RequestOptions,
): Promise<ItemResponse> {
  return request<ItemResponse>("/items", "POST", payload, options);
}

export async function updateItem(
  itemId: number,
  payload: ItemUpdate,
  options?: RequestOptions,
): Promise<ItemResponse> {
  return request<ItemResponse>(`/items/${itemId}`, "PATCH", payload, options);
}

export async function deleteItem(
  itemId: number,
  options?: RequestOptions,
): Promise<void> {
  return request<void>(`/items/${itemId}`, "DELETE", undefined, options);
}

export async function setItemMaintenance(
  itemId: number,
  options?: RequestOptions,
): Promise<ItemResponse> {
  return request<ItemResponse>(`/items/${itemId}/maintenance`, "POST", undefined, options);
}

export async function restoreItemMaintenance(
  itemId: number,
  options?: RequestOptions,
): Promise<ItemResponse> {
  return request<ItemResponse>(`/items/${itemId}/restore-maintenance`, "POST", undefined, options);
}

// ============================================================================
// Members API
// ============================================================================

export async function fetchMembers(
  params?: MemberListParams,
  options?: RequestOptions,
): Promise<MemberResponse[]> {
  const query = buildQueryString(
    params as Record<string, string | number | boolean | null | undefined>,
  );
  return request<MemberResponse[]>(`/members${query}`, "GET", undefined, options);
}

export async function getMember(
  memberId: number,
  options?: RequestOptions,
): Promise<MemberResponse> {
  return request<MemberResponse>(`/members/${memberId}`, "GET", undefined, options);
}

export async function createMember(
  payload: MemberCreate,
  options?: RequestOptions,
): Promise<MemberResponse> {
  return request<MemberResponse>("/members", "POST", payload, options);
}

export async function updateMember(
  memberId: number,
  payload: MemberUpdate,
  options?: RequestOptions,
): Promise<MemberResponse> {
  return request<MemberResponse>(`/members/${memberId}`, "PATCH", payload, options);
}

export async function deleteMember(
  memberId: number,
  options?: RequestOptions,
): Promise<void> {
  return request<void>(`/members/${memberId}`, "DELETE", undefined, options);
}

export async function suspendMember(
  memberId: number,
  options?: RequestOptions,
): Promise<MemberResponse> {
  return request<MemberResponse>(`/members/${memberId}/suspend`, "POST", undefined, options);
}

export async function reinstateMember(
  memberId: number,
  options?: RequestOptions,
): Promise<MemberResponse> {
  return request<MemberResponse>(`/members/${memberId}/reinstate`, "POST", undefined, options);
}

export async function recordPayment(
  memberId: number,
  payload: PaymentCreateRequest,
  options?: RequestOptions,
): Promise<PaymentResponse> {
  return request<PaymentResponse>(`/members/${memberId}/payments`, "POST", payload, options);
}

export async function getMemberStatement(
  memberId: number,
  options?: RequestOptions,
): Promise<MemberStatementResponse> {
  return request<MemberStatementResponse>(`/members/${memberId}/statement`, "GET", undefined, options);
}

// ============================================================================
// Loans API
// ============================================================================

export async function reserveLoan(
  payload: LoanReserveRequest,
  options?: RequestOptions,
): Promise<LoanResponse> {
  return request<LoanResponse>("/loans/reserve", "POST", payload, options);
}

export async function checkoutLoan(
  loanId: number,
  options?: RequestOptions,
): Promise<LoanResponse> {
  return request<LoanResponse>(`/loans/${loanId}/checkout`, "POST", undefined, options);
}

export async function returnLoan(
  loanId: number,
  options?: RequestOptions,
): Promise<LoanResponse> {
  return request<LoanResponse>(`/loans/${loanId}/return`, "POST", undefined, options);
}

export async function cancelLoan(
  loanId: number,
  options?: RequestOptions,
): Promise<LoanResponse> {
  return request<LoanResponse>(`/loans/${loanId}/cancel`, "POST", undefined, options);
}

export async function fetchOverdueLoans(
  params?: OverdueLoansParams,
  options?: RequestOptions,
): Promise<LoanResponse[]> {
  const query = buildQueryString(
    params as Record<string, string | number | boolean | null | undefined>,
  );
  return request<LoanResponse[]>(`/loans/overdue${query}`, "GET", undefined, options);
}

export async function fetchLoans(
  params?: LoanListParams,
  options?: RequestOptions,
): Promise<LoanResponse[]> {
  const query = buildQueryString(
    params as Record<string, string | number | boolean | null | undefined>,
  );
  return request<LoanResponse[]>(`/loans${query}`, "GET", undefined, options);
}

export async function getLoan(
  loanId: number,
  options?: RequestOptions,
): Promise<LoanResponse> {
  return request<LoanResponse>(`/loans/${loanId}`, "GET", undefined, options);
}
