import type {
  AgentAction,
  AgentSession,
  BuildPacket,
  BuildPacketSummary,
  BuildPacketVerification,
  DetachSnapshotResult,
  DueRun,
  Enhancement,
  Evaluation,
  EvidenceReviewCreate,
  Opportunity,
  OpportunityThread,
  OpportunityThreadSummary,
  OpportunityReviewUpdate,
  Integration,
  IntegrationTest,
  LabelOut,
  LocalWorkspace,
  LocalWorkspaceUpdate,
  ProcessSummary,
  ResearchProject,
  ResearchProjectCreate,
  ResearchRun,
  RunDelta,
  Readiness,
  Scan,
  ScanCreate,
  SemanticSearch,
  Source,
  SourceAuthorization,
  SourceRuntimeState,
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
  opportunities: (reviewState?: ReviewState, currentOnly = false) => {
    const params = new URLSearchParams();
    if (reviewState) params.set("review_state", reviewState);
    if (currentOnly) params.set("current_only", "true");
    const query = params.size > 0 ? `?${params}` : "";
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
  researchProject: (id: string) =>
    request<ResearchProject>(`/api/v1/research-projects/${id}`),
  researchProjectRuns: (id: string) =>
    request<ResearchRun[]>(`/api/v1/research-projects/${id}/runs`),
  researchProjectRunDelta: (projectId: string, runId: string) =>
    request<RunDelta>(
      `/api/v1/research-projects/${projectId}/runs/${runId}/delta`,
    ),
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
    request<SemanticSearch>("/api/v1/search", {
      method: "POST",
      body: JSON.stringify({ query, limit: 8 }),
    }),
  opportunityThreads: (filters?: {
    projectId?: string;
    reviewState?: ReviewState;
  }) => {
    const params = new URLSearchParams();
    if (filters?.projectId) params.set("project_id", filters.projectId);
    if (filters?.reviewState) params.set("review_state", filters.reviewState);
    const query = params.size > 0 ? `?${params}` : "";
    return request<OpportunityThreadSummary[]>(
      `/api/v1/opportunity-threads${query}`,
    );
  },
  opportunityThread: (id: string) =>
    request<OpportunityThread>(`/api/v1/opportunity-threads/${id}`),
  updateOpportunityThreadDecision: (
    id: string,
    payload: OpportunityReviewUpdate & { expected_version: number },
  ) =>
    request<OpportunityThread>(`/api/v1/opportunity-threads/${id}/decision`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  detachOpportunitySnapshot: (
    threadId: string,
    snapshotId: string,
    expectedVersion: number,
  ) =>
    request<DetachSnapshotResult>(
      `/api/v1/opportunity-threads/${threadId}/snapshots/${snapshotId}/detach`,
      {
        method: "POST",
        body: JSON.stringify({ expected_version: expectedVersion }),
      },
    ),
  buildPackets: (threadId: string) =>
    request<BuildPacketSummary[]>(
      `/api/v1/opportunity-threads/${threadId}/build-packets`,
    ),
  createBuildPacket: (
    threadId: string,
    payload: { expected_version: number; use_configured_ai: boolean },
  ) =>
    request<BuildPacket>(
      `/api/v1/opportunity-threads/${threadId}/build-packets`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  buildPacket: (packetId: string) =>
    request<BuildPacket>(`/api/v1/build-packets/${packetId}`),
  verifyBuildPacket: (packetId: string) =>
    request<BuildPacketVerification>(
      `/api/v1/build-packets/${packetId}/verify`,
    ),
  downloadBuildPacket: (packetId: string) =>
    download(
      `/api/v1/build-packets/${packetId}/download`,
      `tasksignal-packet-${packetId}.zip`,
    ),
  createDiscourseSource: (name: string) =>
    request<Source>("/api/v1/sources", {
      method: "POST",
      body: JSON.stringify({
        name,
        type: "discourse",
        config_json: {},
        enabled: true,
      }),
    }),
  discourseSourceAuthorization: (sourceId: string) =>
    request<SourceAuthorization>(`/api/v1/sources/${sourceId}/authorization`),
  authorizeDiscourseSource: (sourceId: string, origin: string) =>
    request<SourceAuthorization>(`/api/v1/sources/${sourceId}/authorization`, {
      method: "PUT",
      body: JSON.stringify({ origin, terms_confirmed: true }),
    }),
  revokeDiscourseSource: (sourceId: string) =>
    request<SourceAuthorization>(`/api/v1/sources/${sourceId}/authorization`, {
      method: "DELETE",
    }),
  discourseSourceRuntime: (sourceId: string) =>
    request<SourceRuntimeState>(`/api/v1/sources/${sourceId}/runtime-state`),
  agentSessions: () => request<AgentSession[]>("/api/v1/agent-sessions"),
  approveAgentSession: (
    sessionId: string,
    expectedVersion: number,
    useConfiguredAi: boolean,
  ) =>
    request<AgentSession>(`/api/v1/agent-sessions/${sessionId}/approve`, {
      method: "POST",
      body: JSON.stringify({
        expected_version: expectedVersion,
        use_configured_ai: useConfiguredAi,
      }),
    }),
  revokeAgentSession: (sessionId: string, expectedVersion: number) =>
    request<AgentSession>(`/api/v1/agent-sessions/${sessionId}/revoke`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion }),
    }),
  agentSessionActions: (sessionId: string, limit = 100, offset = 0) =>
    request<AgentAction[]>(
      `/api/v1/agent-sessions/${sessionId}/actions?${new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
      })}`,
    ),
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
