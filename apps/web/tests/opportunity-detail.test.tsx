import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OpportunityDetail } from "../src/features/opportunity-detail";
import type { Opportunity } from "../src/lib/types";

const opportunity: Opportunity = {
  id: "opportunity-1",
  cluster_id: "cluster-1",
  title: "AI-generated code needs production-readiness audits",
  problem_statement: "Teams need evidence-backed checks before shipping AI code.",
  target_user: "Developer-tool founders",
  current_workaround: "Manual review",
  suggested_mvp: "Local audit checklist",
  why_now: "AI-generated code is increasingly common.",
  feasibility_score: 0.82,
  opportunity_score: 0.76,
  competition_notes: "Existing scanners are not local-first.",
  scoring_breakdown_json: {
    frequency: 0.8,
    recency: 0.7,
    pain_intensity: 0.9,
    task_concreteness: 0.75,
    buying_intent: 0.4,
    feasibility: 0.82,
    competition_penalty: 0.1,
    score_formula: "fixture",
    rank_drivers: ["Repeated production-readiness concern"],
    common_phrases: ["production readiness"],
  },
  generated_prompt: "Build a local-first audit workflow.",
  created_at: "2026-06-03T10:00:00.000Z",
  updated_at: "2026-06-03T10:00:00.000Z",
  evidence_items: [
    {
      id: "item-1",
      source: "hackernews",
      external_id: "1",
      url: "https://news.ycombinator.com/item?id=1",
      title: "AI code review",
      body: "We need production-readiness checks for AI-generated code.",
      score: 42,
      comments_count: 7,
      created_at: "2026-06-03T09:30:00.000Z",
      tags: ["ai", "code-review"],
      signal_type: "pain",
      pain_score: 0.9,
      task_concreteness_score: 0.8,
      buying_intent_score: 0.4,
      evidence_spans: ["need production-readiness checks"],
      review_label: null,
      review_note: null,
      reviewed_at: null,
      review_history_count: 0,
    },
  ],
  signal_count: 1,
  top_source: "hackernews",
  review_state: "new",
  review_note: null,
  decision_updated_at: null,
  evidence_readiness: {
    level: "weak",
    evidence_count: 1,
    source_count: 1,
    safe_url_count: 1,
    reviewed_count: 0,
    source_url_coverage: 1,
    human_review_coverage: 0,
    checks: {
      enough_evidence: false,
      source_diversity: false,
      source_url_coverage: true,
      human_review_coverage: false,
    },
    passed_checks: ["source_url_coverage"],
    gaps: [
      "Collect 4 more evidence items.",
      "Add evidence from 1 more source.",
      "Review 1 more evidence item.",
    ],
  },
};

const opportunityWithoutSignalMetadata: Opportunity = {
  ...opportunity,
  signal_count: 0,
  evidence_items: [
    {
      ...opportunity.evidence_items[0],
      id: "item-2",
      external_id: "2",
      title: "Unscored evidence",
      body: "A raw item awaiting signal analysis.",
      score: null,
      comments_count: null,
      tags: [],
      signal_type: null,
      pain_score: null,
      task_concreteness_score: null,
      buying_intent_score: null,
      evidence_spans: [],
    },
  ],
};

const opportunityWithSavedDecision: Opportunity = {
  ...opportunity,
  review_state: "promising",
  review_note: "Server-normalized note.",
  decision_updated_at: "2026-06-03T10:30:00.000Z",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function installLocalStorageMock() {
  const store: Record<string, string> = {};
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => store[key] ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
      clear: vi.fn(() => {
        for (const key of Object.keys(store)) {
          delete store[key];
        }
      }),
    },
  });
}

describe("OpportunityDetail", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    installLocalStorageMock();
  });

  it("renders all three review controls from a complete opportunity response", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/opportunities/opportunity-1")) {
        return Response.json(opportunity);
      }
      return Response.json({ detail: "Unexpected request" }, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<OpportunityDetail id="opportunity-1" />);

    const decision = await screen.findByRole("region", {
      name: "Opportunity decision",
    });
    expect(within(decision).getByLabelText("Decision state")).toHaveValue(
      "new",
    );
    expect(
      screen.getByRole("heading", { name: "Evidence readiness" }),
    ).toBeInTheDocument();
    const evidenceHeading = screen.getByRole("heading", {
      name: "AI code review",
    });
    const evidenceCard = evidenceHeading.closest("article");
    expect(evidenceCard).not.toBeNull();
    expect(within(evidenceCard!).getByText("Evidence review")).toBeInTheDocument();
    expect(within(evidenceCard!).getByLabelText("Evidence label")).toHaveValue(
      "",
    );
    expect(
      within(evidenceCard!).getByRole("button", {
        name: "Add evidence review",
      }),
    ).toBeDisabled();
  });

  it("keeps save success through the real refetch and clears it on a new draft", async () => {
    const saveResponse = deferred<Response>();
    let decisionPersisted = false;
    const fetchMock = vi.fn(
      (
        input: RequestInfo | URL,
        init?: RequestInit,
      ): Promise<Response> => {
        const url = String(input);
        if (
          url.endsWith("/api/opportunities/opportunity-1/review") &&
          init?.method === "PATCH"
        ) {
          return saveResponse.promise;
        }
        if (url.endsWith("/api/opportunities/opportunity-1")) {
          return Promise.resolve(
            Response.json(
              decisionPersisted ? opportunityWithSavedDecision : opportunity,
            ),
          );
        }
        return Promise.resolve(
          Response.json({ detail: "Unexpected request" }, { status: 404 }),
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<OpportunityDetail id="opportunity-1" />);

    const decisionState = await screen.findByLabelText("Decision state");
    fireEvent.change(decisionState, { target: { value: "promising" } });
    fireEvent.change(screen.getByLabelText("Local review note"), {
      target: { value: "  Server-normalized note.  " },
    });
    expect(screen.getByText("Confirmed: New")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/opportunities/opportunity-1/review",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            review_state: "promising",
            review_note: "Server-normalized note.",
          }),
        }),
      );
    });
    expect(screen.getByText("Confirmed: New")).toBeInTheDocument();
    expect(screen.getByLabelText("Decision state")).toHaveValue("promising");
    expect(screen.queryByText("Decision saved")).not.toBeInTheDocument();

    decisionPersisted = true;
    saveResponse.resolve(Response.json(opportunityWithSavedDecision));

    expect(
      await screen.findByText("Confirmed: Promising"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Decision saved")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Local review note")).toHaveValue(
        "Server-normalized note.",
      );
    });

    fireEvent.change(screen.getByLabelText("Decision state"), {
      target: { value: "rejected" },
    });
    expect(screen.getByText("Confirmed: Promising")).toBeInTheDocument();
    expect(screen.queryByText("Decision saved")).not.toBeInTheDocument();
  });

  it("sends the local operator token when enhancing a prompt", async () => {
    window.localStorage.setItem("tasksignal.operatorToken", "local-operator-token");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/opportunities/opportunity-1")) {
        return Response.json(opportunity);
      }
      if (
        url.endsWith("/api/opportunities/opportunity-1/enhance?apply=true")
      ) {
        return Response.json({
          provider: "ollama",
          model: "llama3",
          enhanced_prompt: "Enhanced local-first build prompt.",
          applied: true,
        });
      }
      return Response.json({ detail: "Unexpected request" }, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<OpportunityDetail id="opportunity-1" />);

    const enhanceButton = await screen.findByRole("button", {
      name: /enhance prompt/i,
    });
    await waitFor(() => expect(enhanceButton).toBeEnabled());

    fireEvent.click(enhanceButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://localhost:8000/api/opportunities/opportunity-1/enhance?apply=true",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "X-Operator-Scan-Token": "local-operator-token",
          }),
        }),
      );
    });
    expect(await screen.findByText("Prompt enhanced")).toBeInTheDocument();
  });

  it("keeps prompt enhancement disabled until a local operator token is saved", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/opportunities/opportunity-1")) {
        return Response.json(opportunity);
      }
      return Response.json({ detail: "Unexpected request" }, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<OpportunityDetail id="opportunity-1" />);

    const enhanceButton = await screen.findByRole("button", {
      name: /enhance prompt/i,
    });

    expect(enhanceButton).toBeDisabled();
    expect(
      screen.getByText("Local operator token required"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute(
      "href",
      "/settings",
    );

    fireEvent.click(enhanceButton);

    const calledUrls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(calledUrls.filter((url) => url.includes("/enhance"))).toHaveLength(0);
  });

  it("renders nullable signal metadata as unmeasured", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/opportunities/opportunity-1")) {
        return Response.json(opportunityWithoutSignalMetadata);
      }
      return Response.json({ detail: "Unexpected request" }, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<OpportunityDetail id="opportunity-1" />);

    const heading = await screen.findByRole("heading", {
      name: "Unscored evidence",
    });
    const evidenceCard = heading.closest("article");
    expect(evidenceCard).not.toBeNull();

    const evidence = within(evidenceCard!);
    expect(evidence.getByText("Not classified")).toBeInTheDocument();
    expect(evidence.getAllByText("Not measured")).toHaveLength(3);
    expect(evidence.queryByRole("meter")).not.toBeInTheDocument();
  });

  it("preserves measured signal metadata", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/opportunities/opportunity-1")) {
        return Response.json(opportunity);
      }
      return Response.json({ detail: "Unexpected request" }, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient(<OpportunityDetail id="opportunity-1" />);

    const heading = await screen.findByRole("heading", {
      name: "AI code review",
    });
    const evidenceCard = heading.closest("article");
    expect(evidenceCard).not.toBeNull();

    const evidence = within(evidenceCard!);
    expect(evidence.getByText("pain")).toBeInTheDocument();
    expect(evidence.getByText("90")).toBeInTheDocument();
    expect(evidence.getByText("80")).toBeInTheDocument();
    expect(evidence.getByText("40")).toBeInTheDocument();
    expect(evidence.getAllByRole("meter")).toHaveLength(3);
  });
});
