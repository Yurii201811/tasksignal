import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScanDetail } from "../src/features/scan-detail";
import { Scans } from "../src/features/scans";
import { api } from "../src/lib/api";
import type { Scan } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: {
    scans: vi.fn(),
    scan: vi.fn(),
    createScan: vi.fn(),
  },
}));

const completedScan: Scan = {
  id: "11111111-1111-4111-8111-111111111111",
  source_id: "22222222-2222-4222-8222-222222222222",
  source_type: "hackernews",
  source_name: "Hacker News",
  status: "completed",
  query: "ask",
  started_at: "2026-06-03T10:00:00.000Z",
  finished_at: "2026-06-03T10:00:42.000Z",
  error_message: null,
  items_found: 30,
  items_saved: 18,
  signals_detected: 6,
  clusters_created: 2,
  opportunities_created: 1,
  outcome_message: "The scan generated 1 ranked opportunity from 6 detected signals.",
};

const failedScan: Scan = {
  ...completedScan,
  id: "33333333-3333-4333-8333-333333333333",
  status: "failed",
  finished_at: "2026-06-03T10:01:00.000Z",
  error_message: "Reddit credentials are not configured for this connector.",
  items_found: 0,
  items_saved: 0,
  signals_detected: 0,
  clusters_created: 0,
  opportunities_created: 0,
  outcome_message: "The scan failed before a complete outcome could be computed.",
};

const zeroOpportunityScan: Scan = {
  ...completedScan,
  id: "44444444-4444-4444-8444-444444444444",
  items_found: 14,
  items_saved: 14,
  signals_detected: 0,
  clusters_created: 0,
  opportunities_created: 0,
  outcome_message:
    "The scan saved public records but did not detect concrete problem or task signals.",
};

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("Scans", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("links scan rows to their detail page", async () => {
    vi.mocked(api.scans).mockResolvedValue([completedScan]);

    renderWithClient(<Scans />);

    expect(await screen.findByText("Hacker News")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open/i })).toHaveAttribute(
      "href",
      `/scans/${completedScan.id}`,
    );
  });

  it("renders a completed scan detail with metadata and counts", async () => {
    vi.mocked(api.scan).mockResolvedValue(completedScan);

    renderWithClient(<ScanDetail id={completedScan.id} />);

    expect(await screen.findByText("Scan completed with opportunities")).toBeInTheDocument();
    expect(screen.getAllByText("Hacker News").length).toBeGreaterThan(0);
    expect(screen.getAllByText("30").length).toBeGreaterThan(0);
    expect(screen.getAllByText("18").length).toBeGreaterThan(0);
    expect(screen.getAllByText("6").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
    expect(screen.getByText("60% saved rate")).toBeInTheDocument();
  });

  it("renders completed scans with zero opportunities as an explicit outcome", async () => {
    vi.mocked(api.scan).mockResolvedValue(zeroOpportunityScan);

    renderWithClient(<ScanDetail id={zeroOpportunityScan.id} />);

    expect(await screen.findByText("Scan completed without opportunities")).toBeInTheDocument();
    expect(
      screen.getAllByText(/did not detect concrete problem or task signals/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  });

  it("renders failed scan detail with the redacted API error", async () => {
    vi.mocked(api.scan).mockResolvedValue(failedScan);

    renderWithClient(<ScanDetail id={failedScan.id} />);

    expect(
      await screen.findByText("Scan failed with a redacted message"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(failedScan.error_message as string).length).toBeGreaterThan(0);
  });

  it("shows a clear not-found state when the scan id is missing", async () => {
    vi.mocked(api.scan).mockRejectedValue(
      new Error(JSON.stringify({ detail: "Scan not found" })),
    );

    renderWithClient(<ScanDetail id="missing-scan" />);

    expect((await screen.findAllByText("Scan not found")).length).toBeGreaterThan(0);
  });
});
