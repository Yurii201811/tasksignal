import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueueNextLink } from "../src/components/queue-next-link";
import { QueueReturnLink } from "../src/components/queue-return-link";
import { useUnsavedReview } from "../src/lib/use-unsaved-review";
import { api } from "../src/lib/api";
import { queueOpportunity } from "./fixtures/opportunity";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(window.location.search),
}));
vi.mock("../src/lib/api", () => ({ api: { opportunities: vi.fn() } }));

const rows = ["one", "two", "three"].map((id, index) =>
  queueOpportunity({
    id,
    title: `CI ${id}`,
    problem_statement: "Pipeline reviews",
    target_user: "Maintainers",
    top_source: "github",
    evidence_items: [],
    opportunity_score: 0.9 - index / 10,
    created_at: "2026-09-01T10:00:00Z",
  }),
);

describe("queue review navigation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(api.opportunities).mockResolvedValue(rows);
    window.history.replaceState(
      null,
      "",
      "/opportunities/one?queue=review%3Dnew%26source%3Dgithub%26q%3DCI",
    );
  });

  it("preserves the view and the next neighbor after saving removes the current item", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <QueueReturnLink />
        <QueueNextLink currentId="one" dirty={false} />
      </QueryClientProvider>,
    );
    const next = await screen.findByRole("link", {
      name: "Next in this queue",
    });
    expect(next).toHaveAttribute(
      "href",
      "/opportunities/two?queue=q%3DCI%26review%3Dnew%26source%3Dgithub",
    );
    expect(api.opportunities).toHaveBeenCalledWith({
      currentOnly: true,
      reviewState: "new",
      evidenceSource: "github",
    });
    expect(
      screen.getByRole("link", { name: "Back to filtered queue" }),
    ).toHaveAttribute("href", "/dashboard?q=CI&review=new&source=github");
    vi.mocked(api.opportunities).mockResolvedValue(rows.slice(1));
    await act(async () => {
      await client.invalidateQueries({ queryKey: ["opportunities"] });
    });
    expect(
      screen.getByRole("link", { name: "Next in this queue" }),
    ).toHaveAttribute("href", next.getAttribute("href"));
  });

  it("disables next while editing and moves to the following neighbor on a new item", async () => {
    const client = new QueryClient();
    const view = (currentId: string, dirty: boolean) => (
      <QueryClientProvider client={client}>
        <QueueNextLink currentId={currentId} dirty={dirty} />
      </QueryClientProvider>
    );
    const { rerender } = render(view("one", true));
    expect(
      screen.getByRole("button", { name: "Next in this queue" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("link", { name: "Next in this queue" }),
    ).not.toBeInTheDocument();
    rerender(view("two", false));
    await waitFor(() =>
      expect(
        screen
          .getByRole("link", { name: "Next in this queue" })
          .getAttribute("href"),
      ).toContain("/opportunities/three?queue="),
    );
  });

  it("does not request a queue for standalone detail links", () => {
    vi.mocked(api.opportunities).mockClear();
    window.history.replaceState(null, "", "/opportunities/one");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <QueueNextLink currentId="one" dirty={false} />
      </QueryClientProvider>,
    );
    expect(api.opportunities).not.toHaveBeenCalled();
    expect(screen.queryByText(/end of this queue/)).not.toBeInTheDocument();
  });
});

function ReviewDraft({ dirty }: { dirty: boolean }) {
  useUnsavedReview(dirty);
  return (
    <>
      <a href="/dashboard" onClick={(event) => event.preventDefault()}>
        Leave review
      </a>
      <a href="#evidence">Read evidence</a>
    </>
  );
}

describe("unsaved review warnings", () => {
  it("protects links and reloads while allowing same-page evidence anchors", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { rerender } = render(<ReviewDraft dirty />);
    fireEvent.click(screen.getByRole("link", { name: "Read evidence" }));
    expect(confirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("link", { name: "Leave review" }));
    expect(confirm).toHaveBeenCalledOnce();
    const pending = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(pending);
    expect(pending.defaultPrevented).toBe(true);
    rerender(<ReviewDraft dirty={false} />);
    const clean = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(clean);
    expect(clean.defaultPrevented).toBe(false);
  });
});
