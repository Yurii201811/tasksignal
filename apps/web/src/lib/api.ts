import type {
  DueRun,
  Enhancement,
  Evaluation,
  EvidenceReviewCreate,
  Opportunity,
  OpportunityReviewUpdate,
  Integration,
  IntegrationTest,
  LabelOut,
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
  ReviewState,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function savedOperatorToken(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const token = window.localStorage.getItem("tasksignal.operatorToken")?.trim();
  return token || undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const operatorToken = savedOperatorToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(operatorToken
        ? { "X-Operator-Scan-Token": operatorToken }
        : undefined),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

async function download(path: string, filename: string): Promise<void> {
  const operatorToken = savedOperatorToken();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: operatorToken
      ? { "X-Operator-Scan-Token": operatorToken }
      : undefined,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }

  const objectUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.hidden = true;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  readiness: () => request<Readiness>("/api/readiness"),
  opportunities: (reviewState?: ReviewState) => {
    const query = reviewState
      ? `?${new URLSearchParams({ review_state: reviewState })}`
      : "";
    return request<Opportunity[]>(`/api/opportunities${query}`);
  },
  opportunity: (id: string) => request<Opportunity>(`/api/opportunities/${id}`),
  updateOpportunityReview: (id: string, payload: OpportunityReviewUpdate) =>
    request<Opportunity>(`/api/opportunities/${id}/review`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createEvidenceReview: (payload: EvidenceReviewCreate) =>
    request<LabelOut>("/api/labels", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  itemReviewHistory: (itemId: string) =>
    request<LabelOut[]>(`/api/items/${itemId}/labels`),
  evaluation: () => request<Evaluation>("/api/evaluation"),
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
  validateOperatorToken: (operatorToken: string) =>
    request<Readiness>("/api/readiness", {
      headers: { "X-Operator-Scan-Token": operatorToken },
    }),
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
  downloadPrompt: (id: string) =>
    download(`/api/opportunities/${id}/export.md`, `${id}.md`),
  downloadEvidence: (id: string) =>
    download(`/api/opportunities/${id}/evidence.md`, `evidence-${id}.md`),
  taskPack: (id: string) =>
    request<TaskPack>(`/api/opportunities/${id}/task-pack.json`),
  downloadTaskPack: (id: string) =>
    download(
      `/api/opportunities/${id}/task-pack.md`,
      `tasksignal-task-pack-${id}.md`,
    ),
};
