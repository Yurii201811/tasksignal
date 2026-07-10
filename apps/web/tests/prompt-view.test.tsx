import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PromptView } from "../src/features/prompt-view";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: {
    prompt: vi.fn(),
    downloadTaskPack: vi.fn(),
    downloadEvidence: vi.fn(),
    downloadPrompt: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
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
    vi.mocked(api.downloadTaskPack).mockResolvedValue(undefined);
    vi.mocked(api.downloadEvidence).mockResolvedValue(undefined);
    vi.mocked(api.downloadPrompt).mockResolvedValue(undefined);
  });

  it("downloads all export artifacts through the protected API client", async () => {
    renderWithClient(<PromptView id="opportunity-1" />);

    expect(await screen.findByText("Export readiness")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /task pack/i }));
    fireEvent.click(screen.getByRole("button", { name: /evidence bundle/i }));
    fireEvent.click(screen.getByRole("button", { name: /download \.md/i }));

    await waitFor(() => {
      expect(api.downloadTaskPack).toHaveBeenCalledWith("opportunity-1");
      expect(api.downloadEvidence).toHaveBeenCalledWith("opportunity-1");
      expect(api.downloadPrompt).toHaveBeenCalledWith("opportunity-1");
    });
  });
});
