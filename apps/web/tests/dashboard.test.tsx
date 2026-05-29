import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { describe, expect, it } from "vitest";
import { Dashboard } from "../src/features/dashboard";

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("Dashboard", () => {
  it("renders the main processing action", () => {
    renderWithClient(<Dashboard />);
    expect(screen.getByText("Opportunity dashboard")).toBeInTheDocument();
    expect(screen.getByText("Process demo data")).toBeInTheDocument();
  });
});
