import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CommandMenu } from "../src/components/command-menu";

const destinations = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
];

beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: vi.fn(function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    }),
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: vi.fn(function (this: HTMLDialogElement) {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    }),
  });
});

describe("Quick navigation", () => {
  it("opens with the keyboard shortcut and narrows destinations", () => {
    render(<CommandMenu destinations={destinations} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(
      screen.getByRole("dialog", { name: "Quick navigation" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Find a page or search evidence"), {
      target: { value: "proj" },
    });
    expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute(
      "href",
      "/projects",
    );
    expect(
      screen.queryByRole("link", { name: "Dashboard" }),
    ).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offers an encoded evidence query when no destination matches", () => {
    render(<CommandMenu destinations={destinations} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Open quick navigation" }),
    );
    fireEvent.change(screen.getByLabelText("Find a page or search evidence"), {
      target: { value: "  reports & exports  " },
    });
    expect(
      screen.getByRole("link", {
        name: "Search evidence for “reports & exports”",
      }),
    ).toHaveAttribute("href", "/search?q=reports%20%26%20exports");
  });

  it("clears the old query when reopened and restores focus on close", () => {
    render(<CommandMenu destinations={destinations} />);
    const trigger = screen.getByRole("button", {
      name: "Open quick navigation",
    });
    fireEvent.click(trigger);
    fireEvent.change(screen.getByLabelText("Find a page or search evidence"), {
      target: { value: "reports" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Close quick navigation" }),
    );
    expect(trigger).toHaveFocus();
    fireEvent.click(trigger);
    expect(screen.getByLabelText("Find a page or search evidence")).toHaveValue(
      "",
    );
  });
});
