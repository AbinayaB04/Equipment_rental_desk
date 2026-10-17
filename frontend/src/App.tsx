import { useEffect, useState } from "react";
import { API_BASE_URL, fetchHealth } from "./api/client";

type HealthState =
  | { kind: "loading" }
  | { kind: "ok" }
  | { kind: "error"; message: string };

export default function App() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((body) =>
        setHealth(
          body.status === "ok"
            ? { kind: "ok" }
            : { kind: "error", message: `Unexpected status "${body.status}".` },
        ),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setHealth({
          kind: "error",
          message: error instanceof Error ? error.message : "Unknown error.",
        });
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="page">
      <h1>Equipment Rental Desk</h1>
      <p>Tool library lending desk. The scaffold is in place; the real screens arrive in a later milestone.</p>
      <p role="status">
        Backend:{" "}
        {health.kind === "loading" && "checking…"}
        {health.kind === "ok" && "reachable"}
        {health.kind === "error" && `not reachable. ${health.message}`}
      </p>
      <p className="muted">API: {API_BASE_URL ?? "not configured"}</p>
    </main>
  );
}
