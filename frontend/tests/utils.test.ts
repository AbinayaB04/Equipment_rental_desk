import assert from "node:assert/strict";
import test from "node:test";

import {
  buildQueryString,
  formatPaise,
  formatUtcToIst,
  isLoanActionAllowed,
  isMaintenanceActionAllowed,
  parseRupeesToPaise,
  validateItemForm,
  validateMemberForm,
  validatePaymentForm,
  validateReservationForm,
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

test("validateMemberForm validates valid member inputs", () => {
  const result = validateMemberForm({
    name: "Aarav Sharma",
    phone: "+91-98000-00001",
  });
  assert.equal(result.isValid, true);
  assert.equal(Object.keys(result.errors).length, 0);

  // International/standard phone variations permitted by backend
  const internationalResult = validateMemberForm({
    name: "Priya Patel",
    phone: "9876543210",
  });
  assert.equal(internationalResult.isValid, true);
});

test("validateMemberForm enforces name and phone constraints based on backend rules", () => {
  // Empty inputs
  const emptyResult = validateMemberForm({
    name: "",
    phone: "",
  });
  assert.equal(emptyResult.isValid, false);
  assert.ok(emptyResult.errors.name?.includes("name is required"));
  assert.ok(emptyResult.errors.phone?.includes("Phone number is required"));

  // Whitespace only
  const whitespaceResult = validateMemberForm({
    name: "   ",
    phone: "  ",
  });
  assert.equal(whitespaceResult.isValid, false);
  assert.ok(whitespaceResult.errors.name);
  assert.ok(whitespaceResult.errors.phone);

  // Multiline breaks
  const multilineResult = validateMemberForm({
    name: "Aarav\nSharma",
    phone: "+91-98000\n00001",
  });
  assert.equal(multilineResult.isValid, false);
  assert.ok(multilineResult.errors.name?.includes("single line"));
  assert.ok(multilineResult.errors.phone?.includes("single line"));

  // Length bounds (> 255 chars for name, > 64 chars for phone)
  const lengthResult = validateMemberForm({
    name: "A".repeat(256),
    phone: "1".repeat(65),
  });
  assert.equal(lengthResult.isValid, false);
  assert.ok(lengthResult.errors.name?.includes("255 characters"));
  assert.ok(lengthResult.errors.phone?.includes("64 characters"));
});

test("validatePaymentForm validates valid payment inputs and converts rupees to paise", () => {
  const result = validatePaymentForm({
    amount: "150.50",
    note: "Paid via UPI ref #123456",
  });
  assert.equal(result.isValid, true);
  assert.equal(Object.keys(result.errors).length, 0);
  assert.equal(result.parsedPaise, 15050);

  // Formatted rupee prefix and integer amount
  const intResult = validatePaymentForm({
    amount: "₹500",
  });
  assert.equal(intResult.isValid, true);
  assert.equal(intResult.parsedPaise, 50000);

  // Valid within member's current outstanding balance
  const balanceResult = validatePaymentForm(
    { amount: "200.00" },
    25000, // outstanding balance = 25000 paise (₹250.00)
  );
  assert.equal(balanceResult.isValid, true);
  assert.equal(balanceResult.parsedPaise, 20000);
});

test("validatePaymentForm enforces positive amount, decimal bounds, and overpayment checks", () => {
  // Empty amount
  const emptyResult = validatePaymentForm({ amount: "" });
  assert.equal(emptyResult.isValid, false);
  assert.ok(emptyResult.errors.amount?.includes("amount is required"));

  // Zero amount
  const zeroResult = validatePaymentForm({ amount: "0" });
  assert.equal(zeroResult.isValid, false);
  assert.ok(zeroResult.errors.amount?.includes("greater than ₹0"));

  // Negative amount
  const negativeResult = validatePaymentForm({ amount: "-50" });
  assert.equal(negativeResult.isValid, false);
  assert.ok(negativeResult.errors.amount?.includes("greater than ₹0"));

  // Malformed non-numeric string
  const malformedResult = validatePaymentForm({ amount: "abc" });
  assert.equal(malformedResult.isValid, false);
  assert.ok(malformedResult.errors.amount?.includes("valid rupee amount"));

  // More than 2 decimal places
  const precisionResult = validatePaymentForm({ amount: "10.555" });
  assert.equal(precisionResult.isValid, false);
  assert.ok(precisionResult.errors.amount?.includes("more than 2 decimal places"));

  // Overpayment check against member balance
  const overpayResult = validatePaymentForm(
    { amount: "300.00" },
    25000, // ₹250.00 balance
  );
  assert.equal(overpayResult.isValid, false);
  assert.ok(overpayResult.errors.amount?.includes("exceeds outstanding balance"));

  // Zero balance check
  const zeroBalanceResult = validatePaymentForm(
    { amount: "50.00" },
    0, // ₹0.00 balance
  );
  assert.equal(zeroBalanceResult.isValid, false);
  assert.ok(zeroBalanceResult.errors.amount?.includes("no outstanding fee balance"));

  // Note length constraint (> 255 chars)
  const longNoteResult = validatePaymentForm({
    amount: "50",
    note: "N".repeat(256),
  });
  assert.equal(longNoteResult.isValid, false);
  assert.ok(longNoteResult.errors.note?.includes("255 characters"));

  // Note NUL character rejection
  const nulNoteResult = validatePaymentForm({
    amount: "50",
    note: "Invalid\x00note",
  });
  assert.equal(nulNoteResult.isValid, false);
  assert.ok(nulNoteResult.errors.note?.includes("invalid characters"));
});

test("validateReservationForm validates valid member and item selections", () => {
  const result = validateReservationForm({
    member_id: 1,
    item_id: 5,
  });
  assert.equal(result.isValid, true);
  assert.equal(Object.keys(result.errors).length, 0);
  assert.equal(result.parsedMemberId, 1);
  assert.equal(result.parsedItemId, 5);

  // String numeric IDs from HTML select values
  const stringResult = validateReservationForm({
    member_id: "12",
    item_id: "42",
  });
  assert.equal(stringResult.isValid, true);
  assert.equal(stringResult.parsedMemberId, 12);
  assert.equal(stringResult.parsedItemId, 42);
});

test("validateReservationForm enforces required selections and valid positive IDs", () => {
  // Empty inputs
  const emptyResult = validateReservationForm({
    member_id: "",
    item_id: "",
  });
  assert.equal(emptyResult.isValid, false);
  assert.ok(emptyResult.errors.member_id?.includes("select a member"));
  assert.ok(emptyResult.errors.item_id?.includes("select an equipment item"));

  // Zero IDs
  const zeroResult = validateReservationForm({
    member_id: 0,
    item_id: 0,
  });
  assert.equal(zeroResult.isValid, false);
  assert.ok(zeroResult.errors.member_id);
  assert.ok(zeroResult.errors.item_id);

  // Negative IDs
  const negativeResult = validateReservationForm({
    member_id: -1,
    item_id: -5,
  });
  assert.equal(negativeResult.isValid, false);
  assert.ok(negativeResult.errors.member_id);
  assert.ok(negativeResult.errors.item_id);

  // Non-numeric strings
  const nanResult = validateReservationForm({
    member_id: "abc",
    item_id: "def",
  });
  assert.equal(nanResult.isValid, false);
  assert.ok(nanResult.errors.member_id);
  assert.ok(nanResult.errors.item_id);
});

test("isLoanActionAllowed correctly validates loan state transitions", () => {
  // RESERVED state: can checkout and cancel, cannot return
  assert.equal(isLoanActionAllowed("RESERVED", "checkout"), true);
  assert.equal(isLoanActionAllowed("RESERVED", "cancel"), true);
  assert.equal(isLoanActionAllowed("RESERVED", "return"), false);

  // CHECKED_OUT state: can return, cannot checkout or cancel
  assert.equal(isLoanActionAllowed("CHECKED_OUT", "return"), true);
  assert.equal(isLoanActionAllowed("CHECKED_OUT", "checkout"), false);
  assert.equal(isLoanActionAllowed("CHECKED_OUT", "cancel"), false);

  // RETURNED state (terminal): no actions allowed
  assert.equal(isLoanActionAllowed("RETURNED", "checkout"), false);
  assert.equal(isLoanActionAllowed("RETURNED", "cancel"), false);
  assert.equal(isLoanActionAllowed("RETURNED", "return"), false);

  // CANCELLED state (terminal): no actions allowed
  assert.equal(isLoanActionAllowed("CANCELLED", "checkout"), false);
  assert.equal(isLoanActionAllowed("CANCELLED", "cancel"), false);
  assert.equal(isLoanActionAllowed("CANCELLED", "return"), false);
});

test("validateItemForm edge cases: newline rejection in single-line fields and multiline note support", () => {
  // 1. Name with newline characters is rejected
  const newlineNameResult = validateItemForm({
    name: "Cordless\nDrill",
    category: "Power Tools",
    replacement_value: "5000",
  });
  assert.equal(newlineNameResult.isValid, false);
  assert.ok(newlineNameResult.errors.name?.includes("single line"));

  // Name with carriage return (\r) is rejected
  const crNameResult = validateItemForm({
    name: "Cordless\rDrill",
    category: "Power Tools",
    replacement_value: "5000",
  });
  assert.equal(crNameResult.isValid, false);
  assert.ok(crNameResult.errors.name?.includes("single line"));

  // Name with CRLF (\r\n) is rejected
  const crlfNameResult = validateItemForm({
    name: "Cordless\r\nDrill",
    category: "Power Tools",
    replacement_value: "5000",
  });
  assert.equal(crlfNameResult.isValid, false);
  assert.ok(crlfNameResult.errors.name?.includes("single line"));

  // 2. Category with newline characters is rejected
  const newlineCatResult = validateItemForm({
    name: "Cordless Drill",
    category: "Power\nTools",
    replacement_value: "5000",
  });
  assert.equal(newlineCatResult.isValid, false);
  assert.ok(newlineCatResult.errors.category?.includes("single line"));

  const crlfCatResult = validateItemForm({
    name: "Cordless Drill",
    category: "Power\r\nTools",
    replacement_value: "5000",
  });
  assert.equal(crlfCatResult.isValid, false);
  assert.ok(crlfCatResult.errors.category?.includes("single line"));

  // 3. Multiline condition note is accepted per NoteText schema
  const multilineNoteResult = validateItemForm({
    name: "Hedge Trimmer",
    category: "Garden Tools",
    replacement_value: "7500",
    condition_note: "Blade inspected on Oct 2026.\nMinor scratches on handle.\r\nFully operational with spare battery.",
  });
  assert.equal(multilineNoteResult.isValid, true);
  assert.equal(Object.keys(multilineNoteResult.errors).length, 0);
  assert.equal(multilineNoteResult.parsedPaise, 750000);

  // 4. Condition note with tabs is accepted
  const tabNoteResult = validateItemForm({
    name: "Angle Grinder",
    category: "Power Tools",
    replacement_value: "3500",
    condition_note: "Model:\tAG-200\nVoltage:\t220V",
  });
  assert.equal(tabNoteResult.isValid, true);
  assert.equal(Object.keys(tabNoteResult.errors).length, 0);

  // 5. Existing valid item inputs continue to pass
  const validResult = validateItemForm({
    name: "Rotary Hammer Drill",
    category: "Heavy Duty",
    replacement_value: "15000.50",
    condition_note: "Brand new in box",
  });
  assert.equal(validResult.isValid, true);
  assert.equal(validResult.parsedPaise, 1500050);
});

test("validatePaymentForm edge cases: zero balance, 1-paise boundary, decimal precision, and overpayment checks", () => {
  // 1. A member balance of exactly 0 paise: payment must be rejected
  const zeroBalancePayment = validatePaymentForm({ amount: "10.00" }, 0);
  assert.equal(zeroBalancePayment.isValid, false);
  assert.ok(zeroBalancePayment.errors.amount?.includes("no outstanding fee balance"));

  const zeroBalanceSmallPayment = validatePaymentForm({ amount: "0.01" }, 0);
  assert.equal(zeroBalanceSmallPayment.isValid, false);
  assert.ok(zeroBalanceSmallPayment.errors.amount?.includes("no outstanding fee balance"));

  // 2. A member balance of 1 paise: a valid payment of ₹0.01 should be accepted
  const onePaisePayment = validatePaymentForm({ amount: "0.01" }, 1);
  assert.equal(onePaisePayment.isValid, true);
  assert.equal(onePaisePayment.parsedPaise, 1);
  assert.equal(Object.keys(onePaisePayment.errors).length, 0);

  const onePaiseFormattedPayment = validatePaymentForm({ amount: "₹0.01" }, 1);
  assert.equal(onePaiseFormattedPayment.isValid, true);
  assert.equal(onePaiseFormattedPayment.parsedPaise, 1);

  // Payment of ₹0.02 on 1-paise balance must be rejected as an overpayment
  const onePaiseOverpayment = validatePaymentForm({ amount: "0.02" }, 1);
  assert.equal(onePaiseOverpayment.isValid, false);
  assert.ok(onePaiseOverpayment.errors.amount?.includes("exceeds outstanding balance"));

  // 3. Payment amounts with more than two decimal places must be rejected
  const threeDecimalsPayment = validatePaymentForm({ amount: "0.001" }, 100);
  assert.equal(threeDecimalsPayment.isValid, false);
  assert.ok(threeDecimalsPayment.errors.amount?.includes("more than 2 decimal places"));

  const fourDecimalsPayment = validatePaymentForm({ amount: "25.1234" }, 5000);
  assert.equal(fourDecimalsPayment.isValid, false);
  assert.ok(fourDecimalsPayment.errors.amount?.includes("more than 2 decimal places"));

  // 4. Payment amounts exceeding the outstanding balance must be rejected
  const exceedBalancePayment = validatePaymentForm({ amount: "50.01" }, 5000); // balance is ₹50.00 (5000 paise)
  assert.equal(exceedBalancePayment.isValid, false);
  assert.ok(exceedBalancePayment.errors.amount?.includes("exceeds outstanding balance"));

  const largeExceedPayment = validatePaymentForm({ amount: "500.00" }, 5000);
  assert.equal(largeExceedPayment.isValid, false);
  assert.ok(largeExceedPayment.errors.amount?.includes("exceeds outstanding balance"));

  // Exact balance match is accepted
  const exactBalancePayment = validatePaymentForm({ amount: "50.00" }, 5000);
  assert.equal(exactBalancePayment.isValid, true);
  assert.equal(exactBalancePayment.parsedPaise, 5000);

  // 5. Maximum integer-paise limits (2147483647 paise = ₹21,474,836.47)
  const maxPaisePayment = validatePaymentForm({ amount: "21474836.47" }, 2147483647);
  assert.equal(maxPaisePayment.isValid, true);
  assert.equal(maxPaisePayment.parsedPaise, 2147483647);

  const exceedMaxPaisePayment = validatePaymentForm({ amount: "21474836.48" });
  assert.equal(exceedMaxPaisePayment.isValid, false);
  assert.ok(exceedMaxPaisePayment.errors.amount?.includes("cannot exceed ₹21,474,836.47"));

  // 6. Non-positive amounts rejected
  const zeroPayment = validatePaymentForm({ amount: "0" }, 1000);
  assert.equal(zeroPayment.isValid, false);
  assert.ok(zeroPayment.errors.amount?.includes("greater than ₹0"));

  const negativePayment = validatePaymentForm({ amount: "-5.00" }, 1000);
  assert.equal(negativePayment.isValid, false);
  assert.ok(negativePayment.errors.amount?.includes("greater than ₹0"));
});
