import assert from "node:assert/strict";
import test from "node:test";

import {
  buildQueryString,
  formatPaise,
  formatUtcToIst,
  isMaintenanceActionAllowed,
  parseRupeesToPaise,
  validateItemForm,
} from "../src/api/utils.ts";

test("formatPaise formats integer paise into INR representation without float inaccuracy", () => {
  assert.equal(formatPaise(0), "₹0.00");
  assert.equal(formatPaise(1), "₹0.01");
  assert.equal(formatPaise(50), "₹0.50");
  assert.equal(formatPaise(100), "₹1.00");
  assert.equal(formatPaise(1050), "₹10.50");
  assert.equal(formatPaise(500000), "₹5,000.00");
  assert.equal(formatPaise(2147483647), "₹2,14,74,836.47");
  assert.equal(formatPaise(-150), "-₹1.50");
  assert.equal(formatPaise(NaN), "₹0.00");
  assert.equal(formatPaise(Infinity), "₹0.00");
});

test("parseRupeesToPaise safely parses string and numeric rupee inputs to integer paise", () => {
  assert.equal(parseRupeesToPaise("150.50"), 15050);
  assert.equal(parseRupeesToPaise("₹150.50"), 15050);
  assert.equal(parseRupeesToPaise("10"), 1000);
  assert.equal(parseRupeesToPaise("0"), 0);
  assert.equal(parseRupeesToPaise(""), 0);
  assert.equal(parseRupeesToPaise("   ₹25.75  "), 2575);
  assert.equal(parseRupeesToPaise("5.5"), 550);
  assert.equal(parseRupeesToPaise(150.5), 15050);
  assert.equal(parseRupeesToPaise(-10), 0);
});

test("formatUtcToIst converts ISO UTC timestamp to Asia/Kolkata display", () => {
  // 14:00:00 UTC = 19:30:00 IST (7:30 pm)
  const istFormatted = formatUtcToIst("2026-10-25T14:00:00Z");
  assert.ok(istFormatted.includes("2026"));
  assert.ok(istFormatted.includes("25"));
  assert.ok(istFormatted.includes("Oct"));
  assert.ok(istFormatted.includes("7:30") || istFormatted.includes("19:30"));

  // Date only option
  const dateOnly = formatUtcToIst("2026-10-25T14:00:00Z", { includeTime: false });
  assert.ok(dateOnly.includes("25"));
  assert.ok(dateOnly.includes("2026"));
  assert.ok(!dateOnly.includes("7:30") && !dateOnly.includes("19:30"));

  // Graceful fallback on missing/invalid input
  assert.equal(formatUtcToIst(null), "—");
  assert.equal(formatUtcToIst(undefined), "—");
  assert.equal(formatUtcToIst("invalid-date-string"), "—");
});

test("buildQueryString builds safe URL query strings and omits empty/undefined values", () => {
  // Omit undefined, null, and empty string
  const qs = buildQueryString({
    q: "cordless drill",
    status: undefined,
    category: null,
    empty: "",
    limit: 50,
    offset: 0,
  });

  assert.equal(qs, "?q=cordless+drill&limit=50&offset=0");

  // Empty query string when no valid parameters
  assert.equal(buildQueryString({}), "");
  assert.equal(buildQueryString(undefined), "");
  assert.equal(buildQueryString({ a: undefined, b: null, c: "" }), "");

  // Preserves boolean false and number 0
  const qsWithZero = buildQueryString({ offset: 0, active: false });
  assert.equal(qsWithZero, "?offset=0&active=false");
});

test("validateItemForm validates valid item creation inputs and converts rupees to paise", () => {
  const result = validateItemForm({
    name: "Cordless Drill 18V",
    category: "Power Tools",
    replacement_value: "4500.50",
    condition_note: "Includes two 2Ah batteries.",
  });

  assert.equal(result.isValid, true);
  assert.equal(Object.keys(result.errors).length, 0);
  assert.equal(result.parsedPaise, 450050);

  // Clean INR currency prefix and comma formatted strings
  const formattedInputResult = validateItemForm({
    name: "Angle Grinder",
    category: "Grinders",
    replacement_value: "₹12,500",
  });
  assert.equal(formattedInputResult.isValid, true);
  assert.equal(formattedInputResult.parsedPaise, 1250000);
});

test("validateItemForm enforces field validation, limits, and rejection of invalid values", () => {
  // Empty inputs
  const emptyResult = validateItemForm({
    name: "",
    category: "",
    replacement_value: "",
  });
  assert.equal(emptyResult.isValid, false);
  assert.ok(emptyResult.errors.name);
  assert.ok(emptyResult.errors.category);
  assert.ok(emptyResult.errors.replacement_value);

  // Whitespace only
  const whitespaceResult = validateItemForm({
    name: "   ",
    category: "   ",
    replacement_value: "  ",
  });
  assert.equal(whitespaceResult.isValid, false);
  assert.ok(whitespaceResult.errors.name);
  assert.ok(whitespaceResult.errors.category);

  // Multiline inputs
  const multilineResult = validateItemForm({
    name: "Line 1\nLine 2",
    category: "Cat\nBreak",
    replacement_value: "500",
  });
  assert.equal(multilineResult.isValid, false);
  assert.ok(multilineResult.errors.name?.includes("single line"));
  assert.ok(multilineResult.errors.category?.includes("single line"));

  // Negative and 0 replacement value
  const zeroResult = validateItemForm({
    name: "Drill",
    category: "Tools",
    replacement_value: "0",
  });
  assert.equal(zeroResult.isValid, false);
  assert.ok(zeroResult.errors.replacement_value?.includes("greater than ₹0"));

  const negativeResult = validateItemForm({
    name: "Drill",
    category: "Tools",
    replacement_value: "-500",
  });
  assert.equal(negativeResult.isValid, false);
  assert.ok(negativeResult.errors.replacement_value?.includes("greater than ₹0"));

  // Too many decimal places (> 2)
  const threeDecimalsResult = validateItemForm({
    name: "Drill",
    category: "Tools",
    replacement_value: "50.123",
  });
  assert.equal(threeDecimalsResult.isValid, false);
  assert.ok(threeDecimalsResult.errors.replacement_value?.includes("2 decimal places"));

  // Non-numeric input
  const nonNumericResult = validateItemForm({
    name: "Drill",
    category: "Tools",
    replacement_value: "five hundred",
  });
  assert.equal(nonNumericResult.isValid, false);
  assert.ok(nonNumericResult.errors.replacement_value?.includes("valid rupee amount"));

  // Exceeds 32-bit integer bound (> 2147483647 paise = ₹21,474,836.47)
  const overflowResult = validateItemForm({
    name: "Drill",
    category: "Tools",
    replacement_value: "25000000",
  });
  assert.equal(overflowResult.isValid, false);
  assert.ok(overflowResult.errors.replacement_value?.includes("cannot exceed"));

  // Max lengths (name > 255, category > 100, note > 2000)
  const lengthResult = validateItemForm({
    name: "A".repeat(256),
    category: "B".repeat(101),
    replacement_value: "100",
    condition_note: "C".repeat(2001),
  });
  assert.equal(lengthResult.isValid, false);
  assert.ok(lengthResult.errors.name?.includes("255 characters"));
  assert.ok(lengthResult.errors.category?.includes("100 characters"));
  assert.ok(lengthResult.errors.condition_note?.includes("2000 characters"));
});

test("isMaintenanceActionAllowed correctly determines valid maintenance state transitions", () => {
  assert.equal(isMaintenanceActionAllowed("AVAILABLE"), "set_maintenance");
  assert.equal(isMaintenanceActionAllowed("UNDER_MAINTENANCE"), "restore");
  assert.equal(isMaintenanceActionAllowed("RESERVED"), null);
  assert.equal(isMaintenanceActionAllowed("CHECKED_OUT"), null);
});
