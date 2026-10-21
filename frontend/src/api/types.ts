/**
 * TypeScript type definitions for the Equipment Rental Desk frontend.
 * Accurately matching backend Pydantic models, enums, money units, and error envelopes.
 */

// ============================================================================
// Enums
// ============================================================================

export type ItemStatus = "AVAILABLE" | "RESERVED" | "CHECKED_OUT" | "UNDER_MAINTENANCE";

export type MemberStatus = "ACTIVE" | "SUSPENDED";

export type LoanStatus = "RESERVED" | "CHECKED_OUT" | "RETURNED" | "CANCELLED";

// ============================================================================
// Item Models & Payloads
// ============================================================================

export interface ItemResponse {
  id: number;
  name: string;
  category: string;
  replacement_value: number; // in paise (> 0)
  condition_note: string | null;
  status: ItemStatus;
}

export interface ItemCreate {
  name: string; // 1..255 chars
  category: string; // 1..100 chars
  replacement_value: number; // integer paise (> 0, <= 2147483647)
  condition_note?: string | null; // max 2000 chars
}

export interface ItemUpdate {
  name?: string | null;
  category?: string | null;
  replacement_value?: number | null;
  condition_note?: string | null;
}

export interface ItemListParams {
  q?: string;
  category?: string;
  status?: ItemStatus;
  limit?: number; // 1..500
  offset?: number;
}

// ============================================================================
// Member Models & Payloads
// ============================================================================

export interface MemberResponse {
  id: number;
  name: string;
  phone: string;
  join_date: string; // ISO-8601 UTC timestamp
  status: MemberStatus;
  running_fee_balance: number; // in paise (>= 0)
}

export interface MemberCreate {
  name: string; // 1..255 chars
  phone: string; // 1..64 chars
}

export interface MemberUpdate {
  name?: string | null;
  phone?: string | null;
}

export interface MemberListParams {
  status?: MemberStatus;
  limit?: number;
  offset?: number;
}

export interface MemberStatementResponse {
  member_id: number;
  member: MemberResponse;
  loans: LoanResponse[];
  payments: PaymentResponse[];
  total_fees_charged: number; // in paise
  total_payments_recorded: number; // in paise
  current_outstanding_balance: number; // in paise
}

// ============================================================================
// Loan Models & Payloads
// ============================================================================

export interface LoanResponse {
  id: number;
  member_id: number;
  item_id: number;
  status: LoanStatus;
  reserved_at: string; // ISO-8601 UTC timestamp
  checked_out_at: string | null; // ISO-8601 UTC timestamp
  due_at: string | null; // ISO-8601 UTC timestamp
  returned_at: string | null; // ISO-8601 UTC timestamp
  cancelled_at: string | null; // ISO-8601 UTC timestamp
  fee_charged: number; // in paise (>= 0)
}

export interface LoanReserveRequest {
  member_id: number;
  item_id: number;
}

export interface LoanListParams {
  member_id?: number;
  item_id?: number;
  status?: LoanStatus;
  limit?: number;
  offset?: number;
}

export interface OverdueLoansParams {
  member_id?: number;
  item_id?: number;
  limit?: number;
  offset?: number;
}

// ============================================================================
// Payment Models & Payloads
// ============================================================================

export interface PaymentResponse {
  id: number;
  member_id: number;
  amount: number; // in paise (> 0)
  amount_paise: number; // alias in backend computed field
  paid_at: string; // ISO-8601 UTC timestamp
  note: string | null;
}

export interface PaymentCreateRequest {
  amount_paise: number; // in paise (> 0, <= running_fee_balance)
  note?: string | null;
}

// ============================================================================
// Health & System
// ============================================================================

export interface HealthResponse {
  status: "ok" | string;
  test_clock_enabled?: boolean;
}

// ============================================================================
// Standard Error Response
// ============================================================================

export interface ApiErrorResponse {
  error: string;
  detail: string;
  code: string;
  request_id?: string | null;
}
