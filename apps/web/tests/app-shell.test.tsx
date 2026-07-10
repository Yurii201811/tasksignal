import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../src/components/app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

function installLocalStorageMock(initial: Record<string, string> = {}) {
  const store = { ...initial };
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
    },
  });
}

function renderShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AppShell>Workspace</AppShell>
    </QueryClientProvider>,
  );
}

describe("AppShell hosted API access", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    installLocalStorageMock();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  it("does not show the access control for the loopback development API", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";

    renderShell();

    expect(
      screen.queryByRole("heading", { name: "Unlock protected preview" }),
    ).not.toBeInTheDocument();
  });

  it("stores a trimmed token and unlocks the hosted preview", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ status: "ready" })),
    );
    renderShell();

    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Hosted operator token"), {
      target: { value: "  operator-secret  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock TaskSignal" }));

    await waitFor(() => {
      expect(window.localStorage.setItem).toHaveBeenCalledWith(
        "tasksignal.operatorToken",
        "operator-secret",
      );
      expect(screen.getByText("Protected API unlocked")).toBeInTheDocument();
      expect(screen.getByText("Workspace")).toBeInTheDocument();
    });
  });

  it("keeps the preview locked when token validation fails", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ detail: "Forbidden" }, { status: 403 }),
      ),
    );
    renderShell();

    fireEvent.change(await screen.findByLabelText("Hosted operator token"), {
      target: { value: "wrong-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock TaskSignal" }));

    expect(
      await screen.findByText("The operator token was not accepted."),
    ).toBeInTheDocument();
    expect(window.localStorage.setItem).not.toHaveBeenCalled();
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
  });

  it("shows and clears an existing hosted token", async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.example.test";
    installLocalStorageMock({ "tasksignal.operatorToken": "saved-token" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ status: "ready" })),
    );
    renderShell();

    expect(
      await screen.findByText("Protected API unlocked"),
    ).toBeInTheDocument();
    expect(screen.getByText("Workspace")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Lock preview" }));

    await waitFor(() => {
      expect(window.localStorage.removeItem).toHaveBeenCalledWith(
        "tasksignal.operatorToken",
      );
      expect(
        screen.getByRole("heading", { name: "Unlock protected preview" }),
      ).toBeInTheDocument();
      expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
    });
  });
});
