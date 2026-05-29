import type { Opportunity, ProcessSummary, Scan, Source, Stats } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  opportunities: () => request<Opportunity[]>("/api/opportunities"),
  opportunity: (id: string) => request<Opportunity>(`/api/opportunities/${id}`),
  prompt: (id: string) => request<{ prompt: string }>(`/api/opportunities/${id}/prompt`),
  regenerateOpportunity: (id: string) =>
    request<Opportunity>(`/api/opportunities/${id}/regenerate`, { method: "POST" }),
  processDemo: () => request<ProcessSummary>("/api/process/demo", { method: "POST" }),
  sources: () => request<Source[]>("/api/sources"),
  scans: () => request<Scan[]>("/api/scans"),
  createScan: () => request<Scan>("/api/scans", { method: "POST" }),
  semanticSearch: (query: string) =>
    request<{ items: { item: unknown; similarity: number }[]; opportunities: unknown[] }>("/api/search/semantic", {
      method: "POST",
      body: JSON.stringify({ query, limit: 8 })
    }),
  exportUrl: (id: string) => `${API_BASE}/api/opportunities/${id}/export.md`
};
