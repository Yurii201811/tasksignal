"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Command, Search, X } from "lucide-react";
import { Button, Input } from "./ui";

export type CommandDestination = { href: string; label: string };

export function CommandMenu({
  destinations,
}: {
  destinations: CommandDestination[];
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const normalized = query.trim().toLowerCase();
  const matches = destinations.filter((item) =>
    item.label.toLowerCase().includes(normalized),
  );

  function open() {
    setQuery("");
    dialog.current?.showModal();
  }

  function close() {
    dialog.current?.close();
  }

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === "k" &&
        !event.altKey
      ) {
        event.preventDefault();
        if (dialog.current?.open) dialog.current.close();
        else {
          setQuery("");
          dialog.current?.showModal();
        }
      }
    }
    document.addEventListener("keydown", handleShortcut);
    return () => document.removeEventListener("keydown", handleShortcut);
  }, []);

  return (
    <>
      <Button
        ref={trigger}
        variant="ghost"
        onClick={open}
        aria-label="Open quick navigation"
        aria-haspopup="dialog"
        className="gap-2 text-muted"
      >
        <Search className="h-4 w-4" aria-hidden />
        <span className="hidden sm:inline">Jump to…</span>
        <kbd className="hidden items-center gap-1 rounded border border-border px-1.5 py-0.5 font-mono text-[11px] md:inline-flex">
          <Command className="h-3 w-3" aria-hidden /> K
        </kbd>
      </Button>
      <dialog
        ref={dialog}
        aria-labelledby="command-title"
        className="command-dialog m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl border border-border bg-surface p-0 text-ink shadow-[var(--shadow-overlay)]"
        onClose={() => trigger.current?.focus()}
        onClick={(event) => {
          if (event.target === dialog.current) {
            const bounds = dialog.current.getBoundingClientRect();
            if (
              event.clientX < bounds.left ||
              event.clientX > bounds.right ||
              event.clientY < bounds.top ||
              event.clientY > bounds.bottom
            )
              close();
          }
        }}
      >
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-3">
          <h2 id="command-title" className="text-sm font-semibold">
            Quick navigation
          </h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={close}
            aria-label="Close quick navigation"
          >
            <X className="h-4 w-4" aria-hidden />
          </Button>
        </div>
        <form className="p-4" action="/search" onSubmit={close}>
          <label htmlFor="command-query" className="sr-only">
            Find a page or search evidence
          </label>
          <Input
            id="command-query"
            name="q"
            autoFocus
            autoComplete="off"
            value={query}
            placeholder="Find a page or search evidence…"
            onChange={(event) => setQuery(event.target.value)}
          />
        </form>
        <nav
          aria-label="Quick navigation"
          className="max-h-[50dvh] overflow-y-auto px-3 pb-3"
        >
          {matches.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={close}
              className="group flex min-h-11 items-center justify-between rounded-product px-3 py-2 text-sm hover:bg-surface-muted"
            >
              <span>{item.label}</span>
              <ArrowRight
                className="h-4 w-4 text-muted group-hover:text-signal"
                aria-hidden
              />
            </Link>
          ))}
          {query.trim() ? (
            <Link
              href={`/search?q=${encodeURIComponent(query.trim())}`}
              onClick={close}
              className="mt-2 flex min-h-11 items-center gap-3 rounded-product border-t border-border px-3 py-3 text-sm font-semibold text-signal"
            >
              <Search className="h-4 w-4 shrink-0" aria-hidden />
              <span className="min-w-0 break-words">
                Search evidence for “{query.trim()}”
              </span>
            </Link>
          ) : null}
        </nav>
        <p className="border-t border-border bg-surface-muted px-5 py-3 text-xs text-muted">
          Enter to search · Tab to browse · Esc to close
        </p>
      </dialog>
    </>
  );
}
