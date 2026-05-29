import Link from "next/link";
import { ReactNode } from "react";
import { BarChart3, Database, Home, Radar, Search, Settings, TimerReset } from "lucide-react";

const nav = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/sources", label: "Sources", icon: Database },
  { href: "/scans", label: "Scans", icon: TimerReset },
  { href: "/search", label: "Search", icon: Search },
  { href: "/settings", label: "Settings", icon: Settings }
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <Link href="/" className="flex items-center gap-3 text-ink">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-signal text-white">
            <Radar size={22} />
          </span>
          <span>
            <span className="block text-base font-semibold">TaskSignal</span>
            <span className="block text-xs text-slate-500">Problem discovery engine</span>
          </span>
        </Link>
        <nav className="mt-3 grid grid-cols-3 gap-1">
          {nav.slice(1).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-signal"
            >
              <item.icon size={15} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </header>
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white/82 px-4 py-5 backdrop-blur lg:block">
        <Link href="/" className="flex items-center gap-3 rounded-lg px-2 py-2 text-ink">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-signal text-white">
            <Radar size={22} />
          </span>
          <span>
            <span className="block text-lg font-semibold">TaskSignal</span>
            <span className="block text-xs text-slate-500">Problem discovery engine</span>
          </span>
        </Link>
        <nav className="mt-8 space-y-1">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-signal"
            >
              <item.icon size={17} />
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="lg:pl-64">
        <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
