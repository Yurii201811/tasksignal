"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  ChevronDown,
  ClipboardCheck,
  Database,
  FolderKanban,
  GitBranch,
  HardDrive,
  Home,
  Menu,
  Radar,
  ShieldCheck,
  Search,
  Settings,
  TimerReset,
  type LucideIcon,
} from "lucide-react";
import { api } from "../lib/api";
import { Button, Input } from "./ui";

const NAV_ICON_CLASS = "h-[18px] w-[18px] shrink-0";

const navGroups: {
  label: string;
  items: { href: string; label: string; icon: LucideIcon }[];
}[] = [
  {
    label: "Research",
    items: [
      { href: "/", label: "Home", icon: Home },
      { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
      { href: "/evaluation", label: "Evaluation", icon: ClipboardCheck },
    ],
  },
  {
    label: "Collection",
    items: [
      { href: "/projects", label: "Projects", icon: FolderKanban },
      { href: "/threads", label: "Threads", icon: GitBranch },
      { href: "/sources", label: "Sources", icon: Database },
      { href: "/scans", label: "Scans", icon: TimerReset },
    ],
  },
  {
    label: "Tools",
    items: [
      { href: "/search", label: "Search", icon: Search },
      { href: "/sessions", label: "Agent sessions", icon: ShieldCheck },
      { href: "/settings", label: "Integrations", icon: Settings },
    ],
  },
];

const nav = navGroups.flatMap((group) => group.items);

function isNavActive(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/";
  }
  if (href === "/dashboard" && pathname.startsWith("/opportunities/")) {
    return true;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

const navLinkBase = clsx(
  "whitespace-nowrap rounded-product font-semibold motion-safe:transition-[color,background-color,transform] motion-safe:duration-200 motion-safe:ease-product motion-safe:active:translate-y-px",
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]",
);

function ShellNavLink({
  href,
  label,
  icon: Icon,
  layout,
  active,
}: {
  href: string;
  label: string;
  icon: LucideIcon;
  layout: "desktop" | "mobile";
  active: boolean;
}) {
  if (layout === "desktop") {
    return (
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className={clsx(
          navLinkBase,
          "flex min-h-11 items-center gap-3 px-3 py-2 text-sm",
          active
            ? "bg-[var(--ts-accent-subtle)] font-semibold text-signal"
            : "font-medium text-muted hover:bg-surface-muted hover:text-ink",
        )}
      >
        <Icon className={NAV_ICON_CLASS} aria-hidden />
        <span className="truncate">{label}</span>
      </Link>
    );
  }

  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={clsx(
        navLinkBase,
        "flex min-h-11 min-w-0 items-center gap-2 px-3 py-2 text-sm",
        active
          ? "bg-[var(--ts-accent-subtle)] text-signal"
          : "text-muted hover:bg-surface-muted hover:text-ink",
      )}
    >
      <Icon className={NAV_ICON_CLASS} aria-hidden />
      <span className="max-w-full truncate">{label}</span>
    </Link>
  );
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      href="/"
      className={clsx(
        "flex min-w-0 items-center gap-2 rounded-product px-1 py-1 text-ink",
        navLinkBase,
        "hover:bg-surface-muted",
      )}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-product bg-signal text-[var(--color-accent-ink)]">
        <Radar className="h-5 w-5" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-base font-bold tracking-[-0.02em]">
          TaskSignal
        </span>
        {!compact ? (
          <span className="block truncate text-xs text-muted">
            Problem discovery engine
          </span>
        ) : null}
      </span>
    </Link>
  );
}

function usesHostedApi(apiBase: string | undefined): boolean {
  if (!apiBase) return false;
  try {
    const hostname = new URL(apiBase).hostname;
    return !["localhost", "127.0.0.1", "::1"].includes(hostname);
  } catch {
    return true;
  }
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const hostedApi = usesHostedApi(process.env.NEXT_PUBLIC_API_BASE_URL);
  const [accessState, setAccessState] = useState<
    "loading" | "locked" | "unlocked"
  >("loading");
  const [operatorToken, setOperatorToken] = useState("");
  const [unlocking, setUnlocking] = useState(false);
  const [accessError, setAccessError] = useState<string | null>(null);

  useEffect(() => {
    if (!hostedApi) return;
    const saved = window.localStorage
      .getItem("tasksignal.operatorToken")
      ?.trim();
    if (!saved) {
      setAccessState("locked");
      return;
    }

    let active = true;
    void api
      .validateOperatorToken(saved)
      .then(() => {
        if (active) setAccessState("unlocked");
      })
      .catch(() => {
        if (!active) return;
        window.localStorage.removeItem("tasksignal.operatorToken");
        setAccessError("The saved operator token is no longer valid.");
        setAccessState("locked");
      });
    return () => {
      active = false;
    };
  }, [hostedApi]);

  async function unlockPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = operatorToken.trim();
    if (!token) return;
    setAccessError(null);
    setUnlocking(true);
    try {
      await api.validateOperatorToken(token);
      window.localStorage.setItem("tasksignal.operatorToken", token);
      queryClient.clear();
      setOperatorToken("");
      setAccessState("unlocked");
    } catch {
      setAccessError("The operator token was not accepted.");
    } finally {
      setUnlocking(false);
    }
  }

  function lockPreview() {
    window.localStorage.removeItem("tasksignal.operatorToken");
    queryClient.clear();
    setAccessError(null);
    setAccessState("locked");
  }

  return (
    <div className="min-h-screen bg-[var(--color-paper)]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[var(--z-tooltip)] focus:inline-flex focus:min-h-11 focus:items-center focus:rounded-product focus:border focus:border-border focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-ink focus:shadow-soft focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-[var(--z-sticky)] border-b border-border bg-surface px-4 py-3 lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <BrandMark compact />
          <details key={pathname} className="group relative">
            <summary
              className={clsx(
                navLinkBase,
                "flex min-h-11 cursor-pointer list-none items-center gap-2 border border-border-strong bg-surface px-3 text-sm text-ink hover:bg-surface-muted",
              )}
            >
              <Menu className="h-[18px] w-[18px]" aria-hidden />
              <span>Menu</span>
              <ChevronDown
                className="h-4 w-4 motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-product motion-safe:group-open:rotate-180"
                aria-hidden
              />
            </summary>
            <nav
              className="absolute right-0 top-[calc(100%+0.5rem)] z-[var(--z-dropdown)] grid w-[min(22rem,calc(100vw-2rem))] grid-cols-2 gap-1 rounded-product border border-border bg-surface p-2 shadow-[var(--shadow-overlay)]"
              aria-label="Primary"
            >
              {nav.map((item) => (
                <ShellNavLink
                  key={item.href}
                  {...item}
                  layout="mobile"
                  active={isNavActive(pathname, item.href)}
                />
              ))}
            </nav>
          </details>
        </div>
      </header>

      <aside className="fixed inset-y-0 left-0 z-[var(--z-sticky)] hidden w-60 flex-col overflow-y-auto border-r border-border bg-surface px-3 py-4 lg:flex">
        <BrandMark />
        <nav className="mt-7 space-y-5" aria-label="Primary">
          {navGroups.map((group) => (
            <div key={group.label}>
              <p className="mb-1 px-3 text-xs font-medium text-muted">
                {group.label}
              </p>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <ShellNavLink
                    key={item.href}
                    {...item}
                    layout="desktop"
                    active={isNavActive(pathname, item.href)}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="mt-auto border-t border-border px-3 pt-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <HardDrive className="h-4 w-4 text-signal" aria-hidden />
            Local-first workspace
          </div>
          <p className="mt-1 text-xs leading-5 text-muted">
            Review evidence and exports on this machine.
          </p>
        </div>
      </aside>

      <main
        id="main-content"
        tabIndex={-1}
        className="min-w-0 focus:outline-none lg:pl-60"
      >
        <div className="mx-auto w-full max-w-[90rem] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {hostedApi && accessState === "loading" ? (
            <section
              aria-label="Hosted preview access"
              aria-live="polite"
              className="mb-6 flex items-center gap-3 border-y border-info-border bg-[var(--color-info-surface)] px-4 py-3 text-sm text-info"
            >
              <span className="h-2 w-2 motion-safe:animate-pulse rounded-full bg-info" />
              Checking protected preview access…
            </section>
          ) : null}
          {hostedApi && accessState === "locked" ? (
            <section
              aria-label="Hosted preview access"
              className="mb-6 rounded-product border border-warning-border bg-surface-warning p-4"
            >
              <form
                className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"
                onSubmit={unlockPreview}
              >
                <div className="max-w-2xl">
                  <h2 className="font-semibold text-ink">
                    Unlock protected preview
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-muted">
                    API data and exports stay private until this browser sends
                    the hosted operator token.
                  </p>
                </div>
                <div className="flex w-full flex-col gap-2 sm:flex-row lg:max-w-xl">
                  <label className="min-w-0 flex-1">
                    <span className="sr-only">Hosted operator token</span>
                    <Input
                      type="password"
                      autoComplete="current-password"
                      value={operatorToken}
                      onChange={(event) => setOperatorToken(event.target.value)}
                      placeholder="Hosted operator token"
                      disabled={unlocking}
                    />
                  </label>
                  <Button
                    type="submit"
                    disabled={!operatorToken.trim()}
                    loading={unlocking}
                  >
                    Unlock TaskSignal
                  </Button>
                </div>
              </form>
              {accessError ? (
                <p
                  role="alert"
                  className="mt-3 text-sm font-semibold text-danger"
                >
                  {accessError}
                </p>
              ) : null}
            </section>
          ) : null}
          {hostedApi && accessState === "unlocked" ? (
            <section
              aria-label="Hosted preview access"
              className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-product border border-success-border bg-surface-success px-4 py-3"
            >
              <p className="text-sm font-semibold text-success">
                Protected API unlocked
              </p>
              <Button variant="secondary" size="sm" onClick={lockPreview}>
                Lock preview
              </Button>
            </section>
          ) : null}
          {!hostedApi || accessState === "unlocked" ? children : null}
        </div>
      </main>
    </div>
  );
}
