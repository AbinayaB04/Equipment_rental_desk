import assert from "node:assert/strict";
import test from "node:test";

import {
  ApiClientError,
  cancelLoan,
  checkoutLoan,
  createItem,
  createMember,
  deleteItem,
  deleteMember,
  fetchHealth,
  fetchItems,
  fetchMembers,
  fetchOverdueLoans,
  getGlobalTestClock,
  getItem,
  getMember,
  getMemberStatement,
  recordPayment,
  reserveLoan,
  restoreItemMaintenance,
  returnLoan,
  setBaseUrl,
  setGlobalTestClock,
  setGlobalTestClockKey,
  setItemMaintenance,
  updateItem,
  updateMember,
} from "../src/api/client.ts";

const TEST_BASE_URL = "http://127.0.0.1:8000";

// Helper to mock global fetch
function setupMockFetch(handler: (url: string, init?: RequestInit) => Promise<Response> | Response) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    const urlStr = typeof input === "string" ? input : input.toString();
    return Promise.resolve(handler(urlStr, init));
  }) as typeof fetch;

  return () => {
    globalThis.fetch = originalFetch;
  };
}

test("API client: successful JSON responses and query parameters", async () => {
  setBaseUrl(TEST_BASE_URL);
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;

  const cleanup = setupMockFetch((url, init) => {
    capturedUrl = url;
    capturedInit = init;
    return new Response(
      JSON.stringify([
        {
          id: 1,
          name: "Cordless Drill",
          category: "Drills",
          replacement_value: 50000,
          condition_note: "Good",
          status: "AVAILABLE",
        },
      ]),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  });

  try {
    const items = await fetchItems({ q: "drill", category: "Drills", status: "AVAILABLE", limit: 10, offset: 0 });
    assert.equal(items.length, 1);
    assert.equal(items[0].name, "Cordless Drill");
    assert.equal(items[0].replacement_value, 50000);
    assert.equal(capturedInit?.method, "GET");
    assert.ok(capturedUrl.includes("/items?q=drill&category=Drills&status=AVAILABLE&limit=10&offset=0"));
  } finally {
    cleanup();
  }
});

test("API client: handles 204 No Content without JSON parsing errors", async () => {
  setBaseUrl(TEST_BASE_URL);
  let capturedMethod = "";

  const cleanup = setupMockFetch((_url, init) => {
    capturedMethod = init?.method || "GET";
    return new Response(null, { status: 204 });
  });

  try {
    const itemDeleteResult = await deleteItem(12);
    assert.equal(itemDeleteResult, undefined);
    assert.equal(capturedMethod, "DELETE");

    const memberDeleteResult = await deleteMember(5);
    assert.equal(memberDeleteResult, undefined);
    assert.equal(capturedMethod, "DELETE");
  } finally {
    cleanup();
  }
});

test("API client: parses structured backend error envelopes into ApiClientError", async () => {
  setBaseUrl(TEST_BASE_URL);

  const cleanup = setupMockFetch(() => {
    return new Response(
      JSON.stringify({
        error: "Conflict",
        detail: "Cannot delete member with ID 1 because they have associated loan records.",
        code: "CANNOT_DELETE_ASSOCIATED_RECORDS",
        request_id: "req-abc-123",
      }),
      {
        status: 409,
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "req-abc-123",
        },
      },
    );
  });

  try {
    await deleteMember(1);
    assert.fail("Expected ApiClientError to be thrown");
  } catch (error) {
    assert.ok(error instanceof ApiClientError);
    assert.equal(error.status, 409);
    assert.equal(error.code, "CANNOT_DELETE_ASSOCIATED_RECORDS");
    assert.equal(error.error, "Conflict");
    assert.ok(error.detail.includes("associated loan records"));
    assert.equal(error.requestId, "req-abc-123");
  } finally {
    cleanup();
  }
});

test("API client: handles non-JSON HTTP errors gracefully", async () => {
  setBaseUrl(TEST_BASE_URL);

  const cleanup = setupMockFetch(() => {
    return new Response("Bad Gateway Proxy Error", {
      status: 502,
      statusText: "Bad Gateway",
      headers: { "Content-Type": "text/plain" },
    });
  });

  try {
    await getItem(999);
    assert.fail("Expected ApiClientError to be thrown");
  } catch (error) {
    assert.ok(error instanceof ApiClientError);
    assert.equal(error.status, 502);
    assert.equal(error.code, "HTTP_ERROR");
    assert.ok(error.detail.includes("Bad Gateway"));
  } finally {
    cleanup();
  }
});

test("API client: handles network failures gracefully with NETWORK_ERROR code", async () => {
  setBaseUrl(TEST_BASE_URL);

  const cleanup = setupMockFetch(() => {
    throw new TypeError("Failed to fetch");
  });

  try {
    await fetchMembers();
    assert.fail("Expected ApiClientError to be thrown");
  } catch (error) {
    assert.ok(error instanceof ApiClientError);
    assert.equal(error.status, 0);
    assert.equal(error.code, "NETWORK_ERROR");
    assert.ok(error.detail.includes("Failed to fetch"));
  } finally {
    cleanup();
  }
});

test("API client: reviewer test-clock header behavior", async () => {
  setBaseUrl(TEST_BASE_URL);
  let capturedHeaders: Record<string, string> = {};

  const cleanup = setupMockFetch((_url, init) => {
    capturedHeaders = (init?.headers as Record<string, string>) || {};
    return new Response(JSON.stringify({ status: "ok", test_clock_enabled: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    // 1. By default, no X-Test-Clock header is sent
    setGlobalTestClock(null);
    setGlobalTestClockKey(null);
    await fetchHealth();
    assert.equal(capturedHeaders["X-Test-Clock"], undefined);
    assert.equal(capturedHeaders["X-Test-Clock-Key"], undefined);

    // 2. Per-request test clock option
    const testTimestamp = "2026-10-25T14:00:00Z";
    await fetchHealth(undefined, { testClock: testTimestamp, testClockKey: "key-123" });
    assert.equal(capturedHeaders["X-Test-Clock"], testTimestamp);
    assert.equal(capturedHeaders["X-Test-Clock-Key"], "key-123");

    // 3. Global test clock setting
    setGlobalTestClock(testTimestamp);
    setGlobalTestClockKey("global-key");
    assert.equal(getGlobalTestClock(), testTimestamp);

    await fetchHealth();
    assert.equal(capturedHeaders["X-Test-Clock"], testTimestamp);
    assert.equal(capturedHeaders["X-Test-Clock-Key"], "global-key");

    // 4. Clearing global clock
    setGlobalTestClock(null);
    setGlobalTestClockKey(null);
    assert.equal(getGlobalTestClock(), null);

    await fetchHealth();
    assert.equal(capturedHeaders["X-Test-Clock"], undefined);
  } finally {
    cleanup();
  }
});

test("API client: verified item, member, and loan operations send correct payloads and headers", async () => {
  setBaseUrl(TEST_BASE_URL);
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;

  const cleanup = setupMockFetch((url, init) => {
    capturedUrl = url;
    capturedInit = init;
    return new Response(JSON.stringify({ id: 101 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    // Create item
    await createItem({
      name: "Tiller Pro",
      category: "Garden",
      replacement_value: 35000,
      condition_note: "New",
    });
    assert.equal(capturedUrl, `${TEST_BASE_URL}/items`);
    assert.equal(capturedInit?.method, "POST");
    assert.equal((capturedInit?.headers as Record<string, string>)["Content-Type"], "application/json");
    assert.ok(String(capturedInit?.body).includes("Tiller Pro"));

    // Item maintenance
    await setItemMaintenance(101);
    assert.equal(capturedUrl, `${TEST_BASE_URL}/items/101/maintenance`);

    await restoreItemMaintenance(101);
    assert.equal(capturedUrl, `${TEST_BASE_URL}/items/101/restore-maintenance`);

    // Update item
    await updateItem(101, { name: "Tiller 2.0" });
    assert.equal(capturedUrl, `${TEST_BASE_URL}/items/101`);
    assert.equal(capturedInit?.method, "PATCH");

    // Create member
    await createMember({ name: "Bob", phone: "+91-98765-43210" });
    assert.equal(capturedUrl, `${TEST_BASE_URL}/members`);
    assert.equal(capturedInit?.method, "POST");

    // Member status transitions
    await updateMember(5, { phone: "+91-98765-00000" });
    assert.equal(capturedUrl, `${TEST_BASE_URL}/members/5`);
    assert.equal(capturedInit?.method, "PATCH");

    await getMember(5);
    assert.equal(capturedUrl, `${TEST_BASE_URL}/members/5`);

    // Statement
    await getMemberStatement(5);
    assert.equal(capturedUrl, `${TEST_BASE_URL}/members/5/statement`);

    // Record payment
    await recordPayment(5, { amount_paise: 5000, note: "Cash payoff" });
    assert.equal(capturedUrl, `${TEST_BASE_URL}/members/5/payments`);
    assert.equal(capturedInit?.method, "POST");
    assert.ok(String(capturedInit?.body).includes("5000"));

    // Reserve loan
    await reserveLoan({ member_id: 5, item_id: 101 });
    assert.equal(capturedUrl, `${TEST_BASE_URL}/loans/reserve`);
    assert.equal(capturedInit?.method, "POST");

    // Checkout loan
    await checkoutLoan(77);
    assert.equal(capturedUrl, `${TEST_BASE_URL}/loans/77/checkout`);

    // Return loan
    await returnLoan(77);
    assert.equal(capturedUrl, `${TEST_BASE_URL}/loans/77/return`);

    // Cancel loan
    await cancelLoan(77);
    assert.equal(capturedUrl, `${TEST_BASE_URL}/loans/77/cancel`);

    // Overdue loans
    await fetchOverdueLoans({ limit: 25, offset: 5 });
    assert.equal(capturedUrl, `${TEST_BASE_URL}/loans/overdue?limit=25&offset=5`);
  } finally {
    cleanup();
  }
});

test("API client: fetchMembers and fetchItems support AbortSignal and option error propagation", async () => {
  setBaseUrl(TEST_BASE_URL);

  // 1. Abort handling
  const controller = new AbortController();
  controller.abort();

  const cleanup = setupMockFetch((_url, init) => {
    if (init?.signal?.aborted) {
      const abortErr = new Error("This operation was aborted");
      abortErr.name = "AbortError";
      throw abortErr;
    }
    return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
  });

  try {
    await assert.rejects(
      async () => {
        await fetchMembers({ status: "ACTIVE", limit: 500 }, { signal: controller.signal });
      },
      (err: unknown) => {
        return err instanceof Error && err.name === "AbortError";
      },
    );
  } finally {
    cleanup();
  }

  // 2. HTTP failure during concurrent option fetching produces ApiClientError
  const cleanupError = setupMockFetch((url) => {
    if (url.includes("/items")) {
      return new Response(
        JSON.stringify({
          error: "Internal Server Error",
          detail: "Database query timed out while loading items.",
          code: "DATABASE_TIMEOUT",
        }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(JSON.stringify([{ id: 1, name: "Alice", status: "ACTIVE" }]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    await assert.rejects(
      async () => {
        await Promise.all([
          fetchMembers({ status: "ACTIVE", limit: 500 }),
          fetchItems({ status: "AVAILABLE", limit: 500 }),
        ]);
      },
      (err: unknown) => {
        return (
          err instanceof ApiClientError &&
          err.status === 500 &&
          err.error === "Internal Server Error" &&
          err.detail.includes("timed out")
        );
      },
    );
  } finally {
    cleanupError();
  }
});

test("API client: cancellation behavior distinguishes AbortError from NETWORK_ERROR", async () => {
  setBaseUrl(TEST_BASE_URL);

  // 1. An already-aborted AbortSignal is propagated as an AbortError immediately
  const preAbortedController = new AbortController();
  preAbortedController.abort();

  let fetchInvoked = false;
  const cleanup1 = setupMockFetch(() => {
    fetchInvoked = true;
    return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
  });

  try {
    await assert.rejects(
      async () => {
        await fetchItems({ status: "AVAILABLE" }, { signal: preAbortedController.signal });
      },
      (err: unknown) => {
        assert.ok(err instanceof Error);
        assert.equal(err.name, "AbortError");
        assert.ok(!(err instanceof ApiClientError), "Aborted request must not be converted into ApiClientError");
        return true;
      },
    );
    assert.equal(fetchInvoked, false, "fetch should not be invoked when signal is already aborted");
  } finally {
    cleanup1();
  }

  // 2. An in-flight aborted request is not converted into an ApiClientError with NETWORK_ERROR
  const inFlightController = new AbortController();
  const cleanup2 = setupMockFetch(() => {
    inFlightController.abort();
    const abortErr = new Error("The user aborted a request.");
    abortErr.name = "AbortError";
    throw abortErr;
  });

  try {
    await assert.rejects(
      async () => {
        await fetchMembers({ status: "ACTIVE" }, { signal: inFlightController.signal });
      },
      (err: unknown) => {
        assert.ok(err instanceof Error);
        assert.equal(err.name, "AbortError");
        assert.ok(!(err instanceof ApiClientError), "Aborted request must not become ApiClientError");
        return true;
      },
    );
  } finally {
    cleanup2();
  }

  // 3. Ordinary network failures still produce the expected typed ApiClientError with NETWORK_ERROR
  const cleanup3 = setupMockFetch(() => {
    throw new TypeError("Failed to fetch: Connection refused");
  });

  try {
    await assert.rejects(
      async () => {
        await fetchItems({ status: "AVAILABLE" });
      },
      (err: unknown) => {
        assert.ok(err instanceof ApiClientError);
        assert.equal(err.status, 0);
        assert.equal(err.code, "NETWORK_ERROR");
        assert.equal(err.error, "Network Error");
        assert.ok(err.detail.includes("Connection refused"));
        return true;
      },
    );
  } finally {
    cleanup3();
  }
});

test("API client: URL-encodes query values correctly without splitting on ampersand", async () => {
  setBaseUrl(TEST_BASE_URL);
  let capturedUrl = "";

  const cleanup = setupMockFetch((url) => {
    capturedUrl = url;
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  try {
    await fetchItems({ q: "drill & hammer" });
    assert.ok(
      capturedUrl.includes("/items?q=drill+%26+hammer") ||
        capturedUrl.includes("/items?q=drill%20%26%20hammer"),
      `Expected encoded query parameter in URL, got: ${capturedUrl}`,
    );

    const parsed = new URL(capturedUrl);
    assert.equal(parsed.searchParams.get("q"), "drill & hammer");
    assert.equal(parsed.searchParams.has("hammer"), false);
    assert.equal(Array.from(parsed.searchParams.keys()).length, 1);
  } finally {
    cleanup();
  }
});
