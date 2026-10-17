// The API base URL comes from the environment, never from code.
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL: string | undefined = rawBaseUrl
  ? rawBaseUrl.replace(/\/+$/, "")
  : undefined;

export interface HealthResponse {
  status: string;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  if (!API_BASE_URL) {
    throw new Error(
      "VITE_API_BASE_URL is not set. Copy .env.example to .env in the repository root.",
    );
  }
  const response = await fetch(`${API_BASE_URL}/health`, { signal });
  if (!response.ok) {
    throw new Error(`The API answered with HTTP ${response.status}.`);
  }
  return (await response.json()) as HealthResponse;
}
