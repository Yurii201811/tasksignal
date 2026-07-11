import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sources } from "../src/features/sources";
import { api } from "../src/lib/api";

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

describe("Discourse source management", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.sources).mockResolvedValue([
      {
        id: "source-1",
        name: "Example forum",
        type: "discourse",
        config_json: {},
        enabled: true,
        created_at: "2026-07-11T10:00:00Z",
      },
    ]);
    vi.mocked(api.discourseSourceAuthorization).mockResolvedValue({
      source_id: "source-1",
      source_type: "discourse",
      origin: null,
      host: null,
      port: null,
      authorized: false,
      authorized_at: null,
      terms_confirmed_at: null,
    });
    vi.mocked(api.discourseSourceRuntime).mockResolvedValue({
      source_id: "source-1",
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
    vi.mocked(api.authorizeDiscourseSource).mockResolvedValue({
      source_id: "source-1",
      source_type: "discourse",
      origin: "https://forum.example.com",
      host: "forum.example.com",
      port: 443,
      authorized: true,
      authorized_at: "2026-07-11T10:05:00Z",
      terms_confirmed_at: "2026-07-11T10:05:00Z",
    });
  });

  it("requires explicit terms confirmation before authorizing an exact host", async () => {
    renderFeature();

    expect(
      await screen.findByText("Discourse authorization"),
    ).toBeInTheDocument();
    const authorize = await screen.findByRole("button", {
      name: "Authorize exact host",
    });
    expect(authorize).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Exact HTTPS forum origin"), {
      target: { value: "https://forum.example.com" },
    });
    fireEvent.click(
      screen.getByRole("checkbox", { name: /confirm.*public forum.*terms/i }),
    );
    fireEvent.click(authorize);

    await waitFor(() =>
      expect(api.authorizeDiscourseSource).toHaveBeenCalledWith(
        "source-1",
        "https://forum.example.com",
      ),
    );
    expect(screen.getByText(/public only.*no cookies/i)).toBeInTheDocument();
  });

  it("requires fresh terms confirmation whenever the exact origin changes", async () => {
    renderFeature();

    const origin = await screen.findByLabelText("Exact HTTPS forum origin");
    const terms = screen.getByRole("checkbox", {
      name: /confirm.*public forum.*terms/i,
    });
    const authorize = screen.getByRole("button", {
      name: "Authorize exact host",
    });

    fireEvent.change(origin, {
      target: { value: "https://forum-a.example.com" },
    });
    fireEvent.click(terms);
    expect(terms).toBeChecked();
    expect(authorize).toBeEnabled();

    fireEvent.change(origin, {
      target: { value: "https://forum-b.example.com" },
    });

    expect(terms).not.toBeChecked();
    expect(authorize).toBeDisabled();
    fireEvent.click(terms);
    fireEvent.click(authorize);
    await waitFor(() =>
      expect(api.authorizeDiscourseSource).toHaveBeenCalledWith(
        "source-1",
        "https://forum-b.example.com",
      ),
    );
  });
});
