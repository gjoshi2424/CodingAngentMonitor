import { Session, StepResult } from "./types";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export const ROUTES = {
  health: "/",
  analyzeMock: "/analyze/mock",
  analyzeLive: "/analyze/live",
  watch: "/watch",
  sessions: "/sessions",
  session: (id: number) => `/sessions/${id}`,
} as const;

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

/** Authorization header for regular fetch calls. */
function authHeaders(): HeadersInit {
  return API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {};
}

/**
 * Returns a full URL with ?api_key=… appended when a key is configured.
 * Used for EventSource connections, which cannot send custom headers.
 */
export function sseUrl(route: string): string {
  const url = `${BASE_URL}${route}`;
  if (!API_KEY) return url;
  return `${url}?api_key=${encodeURIComponent(API_KEY)}`;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export async function getSessions(): Promise<Session[]> {
  const res = await fetch(`${BASE_URL}${ROUTES.sessions}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`);
  return res.json();
}

export async function getSession(
  id: number
): Promise<{ session: Session; steps: StepResult[] }> {
  const res = await fetch(`${BASE_URL}${ROUTES.session(id)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to fetch session ${id}: ${res.status}`);
  return res.json();
}
