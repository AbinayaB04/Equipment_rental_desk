/**
 * Shared utility functions for monetary formatting, IST datetime display,
 * safe query string generation, and item form validation.
 */

import type { ItemStatus } from "./types.ts";

/**
 * Shared maximum 32-bit signed integer boundary (PostgreSQL INTEGER range).
 */
export const MAX_REPLACEMENT_PAISE = 2_147_483_647;

/**
 * Format an integer paise value into Indian Rupee display (e.g. 50000 paise -> "₹500.00").
 * Strictly avoids floating point arithmetic and rounding errors.
 */
export function formatPaise(paise: number): string {
  if (!Number.isFinite(paise)) {
    return "₹0.00";
  }

  const isNegative = paise < 0;
  const absPaise = Math.abs(Math.trunc(paise));
  const rupees = Math.floor(absPaise / 100);
  const remainder = absPaise % 100;
  const remainderStr = remainder.toString().padStart(2, "0");

  const formattedRupees = new Intl.NumberFormat("en-IN").format(rupees);
  return `${isNegative ? "-" : ""}₹${formattedRupees}.${remainderStr}`;
}

/**
 * Safely parse a rupee string (e.g. "150.50" or "₹150.50") into integer paise (15050)
 * without floating point arithmetic or roundoff error.
 */
export function parseRupeesToPaise(input: string | number): number {
  if (typeof input === "number") {
    if (!Number.isFinite(input) || input <= 0) return 0;
    return Math.round(input * 100);
  }

  const cleaned = input.trim().replace(/^₹/, "").trim().replace(/,/g, "");
  if (!cleaned) return 0;

  const parts = cleaned.split(".");
  const rupees = parseInt(parts[0] || "0", 10);
  if (Number.isNaN(rupees) || rupees < 0) return 0;

  let paise = 0;
  if (parts.length > 1) {
    const decimalPart = parts[1].slice(0, 2).padEnd(2, "0");
    paise = parseInt(decimalPart, 10);
    if (Number.isNaN(paise) || paise < 0) paise = 0;
  }

  return rupees * 100 + paise;
}

export interface DateFormatOptions {
  includeTime?: boolean;
  includeSeconds?: boolean;
}

/**
 * Format an ISO-8601 UTC timestamp into a human-readable string in Asia/Kolkata (IST).
 */
export function formatUtcToIst(
  isoString: string | Date | null | undefined,
  options?: DateFormatOptions,
): string {
  if (!isoString) return "—";

  const date = typeof isoString === "string" ? new Date(isoString) : isoString;
  if (Number.isNaN(date.getTime())) return "—";

  const includeTime = options?.includeTime ?? true;
  const includeSeconds = options?.includeSeconds ?? false;

  const formatter = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(includeTime
      ? {
          hour: "numeric",
          minute: "2-digit",
          ...(includeSeconds ? { second: "2-digit" } : {}),
          hour12: true,
        }
      : {}),
  });

  return formatter.format(date);
}

/**
 * Build a URL query string omitting undefined, null, or empty string values.
 * Preserves 0 and false as valid query values.
 */
export function buildQueryString(
  params?: Record<string, string | number | boolean | null | undefined>,
): string {
  if (!params) return "";

  const entries = Object.entries(params)
    .filter(([_, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => [key, String(value)]);

  if (entries.length === 0) return "";

  const searchParams = new URLSearchParams(entries);
  return `?${searchParams.toString()}`;
}

// ============================================================================
// Item Form Validation
// ============================================================================

export interface ItemFormValues {
  name: string;
  category: string;
  replacement_value: string;
  condition_note?: string;
}

export interface ItemFormValidationResult {
  isValid: boolean;
  errors: {
    name?: string;
    category?: string;
    replacement_value?: string;
    condition_note?: string;
  };
  parsedPaise?: number;
}

/**
 * Validate item creation form inputs against domain rules and schema limits.
 * Guarantees exact integer paise conversion without floating point inaccuracies.
 */
export function validateItemForm(values: ItemFormValues): ItemFormValidationResult {
  const errors: ItemFormValidationResult["errors"] = {};

  // 1. Name validation
  const cleanName = values.name ? values.name.trim() : "";
  if (!cleanName) {
    errors.name = "Equipment name is required.";
  } else if (cleanName.length > 255) {
    errors.name = "Equipment name cannot exceed 255 characters.";
  } else if (/[\r\n\t]/.test(cleanName)) {
    errors.name = "Equipment name must be a single line.";
  }

  // 2. Category validation
  const cleanCategory = values.category ? values.category.trim() : "";
  if (!cleanCategory) {
    errors.category = "Category is required.";
  } else if (cleanCategory.length > 100) {
    errors.category = "Category cannot exceed 100 characters.";
  } else if (/[\r\n\t]/.test(cleanCategory)) {
    errors.category = "Category must be a single line.";
  }

  // 3. Replacement value validation
  const rawValue = values.replacement_value
    ? values.replacement_value.trim().replace(/^₹/, "").trim().replace(/,/g, "")
    : "";
  let parsedPaise: number | undefined;

  if (!rawValue) {
    errors.replacement_value = "Replacement value is required.";
  } else if (rawValue.startsWith("-")) {
    errors.replacement_value = "Replacement value must be greater than ₹0.";
  } else if (!/^\d+(\.\d+)?$/.test(rawValue)) {
    errors.replacement_value = "Please enter a valid rupee amount (e.g. 5000 or 5000.50).";
  } else {
    const parts = rawValue.split(".");
    if (parts.length > 1 && parts[1].length > 2) {
      errors.replacement_value = "Replacement value cannot have more than 2 decimal places.";
    } else {
      const paise = parseRupeesToPaise(rawValue);
      if (paise <= 0) {
        errors.replacement_value = "Replacement value must be greater than ₹0.";
      } else if (paise > MAX_REPLACEMENT_PAISE) {
        errors.replacement_value = "Replacement value cannot exceed ₹21,474,836.47.";
      } else {
        parsedPaise = paise;
      }
    }
  }

  // 4. Condition note validation (optional, max 2000 chars)
  if (values.condition_note && values.condition_note.length > 2000) {
    errors.condition_note = "Condition note cannot exceed 2000 characters.";
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
    parsedPaise,
  };
}

/**
 * Determine which maintenance action, if any, is appropriate for an item's status.
 * - AVAILABLE -> "set_maintenance" (allow marking under maintenance)
 * - UNDER_MAINTENANCE -> "restore" (allow restoring to service)
 * - RESERVED / CHECKED_OUT -> null (do not show inappropriate actions)
 */
export function isMaintenanceActionAllowed(status: ItemStatus): "set_maintenance" | "restore" | null {
  if (status === "AVAILABLE") return "set_maintenance";
  if (status === "UNDER_MAINTENANCE") return "restore";
  return null;
}
