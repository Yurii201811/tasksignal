"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  ClipboardCheck,
  Database,
  FolderKanban,
  Home,
  Radar,
  Search,
  Settings,
  TimerReset,
  type LucideIcon,
} from "lucide-react";
import { api } from "../lib/api";
import { Button, Input } from "./ui";

const NAV_ICON_CLASS = "h-[18px] w-[18px] shrink-0";

const nav: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/evaluation", label: "Evaluation", icon: ClipboardCheck },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/sources", label: "Sources", icon: Database },
  { href: "/scans", label: "Scans", icon: TimerReset },
  { href: "/search", label: "Search", icon: Search },
  { href: "/settings", label: "Integrations", icon: Settings },
];

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
  "rounded-product font-semibold motion-safe:transition-[color,background-color] motion-safe:duration-200 motion-safe:ease-product",
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
        "flex min-h-11 min-w-0 flex-col items-center justify-center gap-1 px-1 py-2",
        active
          ? "bg-[var(--ts-accent-subtle)] text-signal"
          : "text-muted hover:bg-surface-muted hover:text-ink",
      )}
    >
      <Icon className={NAV_ICON_CLASS} aria-hidden />
      <span className="max-w-full truncate text-center text-[11px] leading-none whitespace-nowrap">
        {label}
      </span>
    </Link>
  );
}

function BrandMark() {
  return (
    <Link
      href="/"
      className={clsx(
        "flex min-w-0 items-center gap-3 rounded-product text-ink",
        navLinkBase,
        "hover:bg-surface-muted",
      )}
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-product bg-signal text-[color-mix(in_srgb,var(--ts-surface)_96%,transparent)]">
        <Radar className="h-[22px] w-[22px]" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-base font-semibold lg:text-lg">
          TaskSignal
        </span>
        <span className="block truncate text-xs text-muted">
          Problem discovery engine
        </span>
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
    <div className="min-h-screen">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:inline-flex focus:min-h-11 focus:items-center focus:rounded-product focus:border focus:border-border focus:bg-surface focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-ink focus:shadow-soft focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
      >
        Skip to content
      </a>

      <header className="border-b border-border bg-surface px-4 py-3 lg:hidden">
        <BrandMark />
        <nav className="mt-3 grid grid-cols-4 gap-1" aria-label="Primary">
          {nav.map((item) => (
            <ShellNavLink
              key={item.href}
              {...item}
              layout="mobile"
              active={isNavActive(pathname, item.href)}
            />
          ))}
        </nav>
      </header>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-border bg-surface px-4 py-5 lg:block">
        <BrandMark />
        <nav className="mt-8 space-y-1" aria-label="Primary">
          {nav.map((item) => (
            <ShellNavLink
              key={item.href}
              {...item}
              layout="desktop"
              active={isNavActive(pathname, item.href)}
            />
          ))}
        </nav>
      </aside>

      <main id="main-content" tabIndex={-1} className="min-w-0 lg:pl-64">
        <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
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
