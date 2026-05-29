import { clsx } from "clsx";
import Link from "next/link";
import { ReactNode } from "react";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={clsx("rounded-lg border border-slate-200 bg-white p-5 shadow-soft", className)}>{children}</section>;
}

export function Badge({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "green" | "amber" | "blue" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    blue: "bg-sky-50 text-sky-700"
  };
  return <span className={clsx("inline-flex rounded-md px-2 py-1 text-xs font-semibold", tones[tone])}>{children}</span>;
}

export function ButtonLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="inline-flex items-center justify-center rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700">
      {children}
    </Link>
  );
}

export function ScoreBar({ value }: { value: number }) {
  return (
    <div className="h-2 w-full rounded-full bg-slate-100">
      <div className="h-2 rounded-full bg-signal" style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

