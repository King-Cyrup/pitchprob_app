import "server-only";
import { notFound } from "next/navigation";
import type {
  InsightsResponse,
  MatchDetails,
  MatchesResponse,
  ResultsDaysResponse,
  ResultsResponse,
} from "@/lib/types";

const apiBaseUrl = (process.env.API_BASE_URL || "http://127.0.0.1:8080").replace(/\/+$/, "");
const requestTimeoutMs = 10_000;

function headers(): HeadersInit {
  const user = process.env.API_USER;
  const password = process.env.API_PASSWORD;
  if ((user && !password) || (!user && password)) {
    throw new Error("Set both API_USER and API_PASSWORD, or leave both unset.");
  }
  if (!user || !password) return {};
  return { Authorization: `Basic ${Buffer.from(`${user}:${password}`).toString("base64")}` };
}

async function get<T>(path: string, revalidate = 0): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      headers: headers(),
      cache: revalidate ? "force-cache" : "no-store",
      signal: AbortSignal.timeout(requestTimeoutMs),
      ...(revalidate ? { next: { revalidate } } : {}),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      throw new Error("The PitchProb data service did not respond within 10 seconds.");
    }
    throw error;
  }
  if (response.status === 404) notFound();
  if (!response.ok) {
    throw new Error(`The PitchProb data service returned ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function getMatches(date: string): Promise<MatchesResponse> {
  return get(`/api/matches?date=${encodeURIComponent(date)}`);
}

export function getMatch(id: number): Promise<MatchDetails> {
  return get(`/api/matches/${id}`);
}

export function getResultsDays(): Promise<ResultsDaysResponse> {
  return get("/api/results/days");
}

export function getResults(date: string): Promise<ResultsResponse> {
  return get(`/api/results?date=${encodeURIComponent(date)}`);
}

export function getInsights(source: "live" | "backtest"): Promise<InsightsResponse> {
  return get(`/api/insights?source=${source}`, 300);
}
