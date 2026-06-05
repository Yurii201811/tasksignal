import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PromptView } from "../src/features/prompt-view";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: {
    prompt: vi.fn(),
    taskPackExportUrl: vi.fn((id: string) => `http://localhost:8000/api/opportunities/${id}/task-pack.md`),
    evidenceExportUrl: vi.fn((id: string) => `http://localhost:8000/api/opportunities/${id}/evidence.md`),
    promptExportUrl: vi.fn((id: string) => `http://localhost:8000/api/opportunities/${id}/export.md`),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("PromptView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.prompt).mockResolvedValue({
      prompt: [
        "# Build prompt",
        "",
        "## Evidence",
        "Source excerpts stay visible.",
        "",
        "## Ranking rationale",
        "Score drivers stay visible.",
        "",
        "## Trust and privacy constraints",
        "No raw usernames or secrets.",
      ].join("\n"),
    });
  });

  it("links all export artifacts from the prompt screen", async () => {
    renderWithClient(<PromptView id="opportunity-1" />);

    expect(await screen.findByText("Export readiness")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /task pack/i })).toHaveAttribute(
      "href",
      "http://localhost:8000/api/opportunities/opportunity-1/task-pack.md",
    );
    expect(screen.getByRole("link", { name: /evidence bundle/i })).toHaveAttribute(
      "href",
      "http://localhost:8000/api/opportunities/opportunity-1/evidence.md",
    );
    expect(screen.getByRole("link", { name: /download \.md/i })).toHaveAttribute(
      "href",
      "http://localhost:8000/api/opportunities/opportunity-1/export.md",
    );
  });
});
