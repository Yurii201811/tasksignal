import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "../src/components/app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/evaluation" }));

describe("AppShell", () => {
  it("marks Evaluation as the active navigation destination", () => {
    render(
      <AppShell>
        <p>Content</p>
      </AppShell>,
    );
    for (const link of screen.getAllByRole("link", { name: "Evaluation" })) {
      expect(link).toHaveAttribute("href", "/evaluation");
      expect(link).toHaveAttribute("aria-current", "page");
    }
  });
});
