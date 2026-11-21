import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sources } from "../src/features/sources";
import { api } from "../src/lib/api";
import type { Source } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: {
    sources: vi.fn(),
    createDiscourseSource: vi.fn(),
    discourseSourceAuthorization: vi.fn(),
    authorizeDiscourseSource: vi.fn(),
    revokeDiscourseSource: vi.fn(),
    discourseSourceRuntime: vi.fn(),
  },
}));

function source(
  overrides: Partial<Source> & Pick<Source, "id" | "name" | "type">,
): Source {
  return {
    config_json: {},
    enabled: true,
    created_at: "2026-09-01T09:00:00Z",
    ...overrides,
  };
}

function renderFeature() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <Sources />
    </QueryClientProvider>,
  );
}

describe("Sources", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.discourseSourceAuthorization).mockResolvedValue({
      source_id: "forum-a",
      source_type: "discourse",
      origin: null,
      host: null,
      port: null,
      authorized: false,
      authorized_at: null,
      terms_confirmed_at: null,
    });
    vi.mocked(api.discourseSourceRuntime).mockResolvedValue({
      source_id: "forum-a",
      origin: null,
      readiness: "terms_required",
      can_run: false,
      last_success_at: null,
      last_failure_at: null,
      last_failure_code: null,
      last_failure_message: null,
      last_http_status: null,
      retry_after_at: null,
    });
  });

  it("does not claim the registry is empty when the load fails, and retries", async () => {
    vi.mocked(api.sources)
      .mockRejectedValueOnce(new Error('{"detail":"Registry unavailable"}'))
      .mockResolvedValue([
        source({ id: "hn", name: "Hacker News", type: "hackernews" }),
      ]);
    renderFeature();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load sources");
    expect(alert).toHaveTextContent("Registry unavailable");
    expect(
      screen.queryByText("No sources are registered"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: "Hacker News API" }),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.sources).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the empty registry state only after a successful empty load", async () => {
    vi.mocked(api.sources).mockResolvedValue([]);
    renderFeature();

    expect(
      await screen.findByText("No sources are registered"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps each Discourse forum's own name instead of a shared connector label", async () => {
    vi.mocked(api.sources).mockResolvedValue([
      source({ id: "forum-a", name: "Maintainers forum", type: "discourse" }),
      source({ id: "forum-b", name: "Indie hackers forum", type: "discourse" }),
      source({ id: "fixture", name: "fixture", type: "fixture" }),
    ]);
    renderFeature();

    expect(
      await screen.findByRole("heading", {
        name: "Maintainers forum",
        level: 2,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Indie hackers forum", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Fixture files", level: 2 }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Discourse forum", level: 2 }),
    ).not.toBeInTheDocument();
  });
});
