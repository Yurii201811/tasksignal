import type {
  DueRun,
  Enhancement,
  Opportunity,
  Integration,
  IntegrationTest,
  LocalWorkspace,
  LocalWorkspaceUpdate,
  ProcessSummary,
  ResearchProject,
  ResearchProjectCreate,
  Readiness,
  Scan,
  ScanCreate,
  Source,
  Stats,
  TaskPack,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  readiness: () => request<Readiness>("/api/readiness"),
  opportunities: () => request<Opportunity[]>("/api/opportunities"),
  opportunity: (id: string) => request<Opportunity>(`/api/opportunities/${id}`),
  prompt: (id: string) =>
    request<{ prompt: string }>(`/api/opportunities/${id}/prompt`),
  regenerateOpportunity: (id: string) =>
    request<Opportunity>(`/api/opportunities/${id}/regenerate`, {
      method: "POST",
    }),
  enhanceOpportunity: (id: string, apply = false, operatorToken?: string) =>
    request<Enhancement>(`/api/opportunities/${id}/enhance?apply=${apply}`, {
      method: "POST",
      headers: operatorToken
        ? { "X-Operator-Scan-Token": operatorToken }
        : undefined,
    }),
  processDemo: () =>
    request<ProcessSummary>("/api/process/demo", { method: "POST" }),
  sources: () => request<Source[]>("/api/sources"),
  integrations: () => request<Integration[]>("/api/integrations"),
  localWorkspace: () => request<LocalWorkspace>("/api/local-workspace"),
  updateLocalWorkspace: (payload: LocalWorkspaceUpdate) =>
    request<LocalWorkspace>("/api/local-workspace", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  testIntegration: (id: string, operatorToken?: string) =>
    request<IntegrationTest>(`/api/integrations/${id}/test`, {
      method: "POST",
      headers: operatorToken
        ? { "X-Operator-Scan-Token": operatorToken }
        : undefined,
    }),
  researchProjects: () => request<ResearchProject[]>("/api/research-projects"),
  createResearchProject: (payload: ResearchProjectCreate) =>
    request<ResearchProject>("/api/research-projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runResearchProject: (id: string, operatorToken?: string) =>
    request<Scan>(`/api/research-projects/${id}/run`, {
      method: "POST",
      headers: operatorToken
        ? { "X-Operator-Scan-Token": operatorToken }
        : undefined,
    }),
  runDueResearchProjects: (operatorToken?: string) =>
    request<DueRun>("/api/research-projects/run-due", {
      method: "POST",
      headers: operatorToken
        ? { "X-Operator-Scan-Token": operatorToken }
        : undefined,
    }),
  scans: () => request<Scan[]>("/api/scans"),
  scan: (id: string) => request<Scan>(`/api/scans/${id}`),
  createScan: (payload: ScanCreate) =>
    request<Scan>("/api/scans", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  semanticSearch: (query: string) =>
    request<{
      items: { item: unknown; similarity: number }[];
      opportunities: unknown[];
    }>("/api/search/semantic", {
      method: "POST",
      body: JSON.stringify({ query, limit: 8 }),
    }),
  promptExportUrl: (id: string) =>
    `${API_BASE}/api/opportunities/${id}/export.md`,
  evidenceExportUrl: (id: string) =>
    `${API_BASE}/api/opportunities/${id}/evidence.md`,
  taskPack: (id: string) =>
    request<TaskPack>(`/api/opportunities/${id}/task-pack.json`),
  taskPackExportUrl: (id: string) =>
    `${API_BASE}/api/opportunities/${id}/task-pack.md`,
  exportUrl: (id: string) => `${API_BASE}/api/opportunities/${id}/export.md`,
};
