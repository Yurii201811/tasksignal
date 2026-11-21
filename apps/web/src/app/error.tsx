"use client";

import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <section className="mx-auto max-w-xl py-16 sm:py-24" role="alert">
      <p className="eyebrow text-danger">Something interrupted this page</p>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">
        Let’s get your research back on screen.
      </h1>
      <p className="mt-4 text-base leading-7 text-muted">
        This page could not finish loading. Try opening it again, or return to
        the workspace and choose another view.
      </p>
      <div className="mt-7 flex flex-wrap items-center gap-3">
        <Button onClick={reset}>
          <RefreshCw className="h-4 w-4" aria-hidden />
          Try again
        </Button>
        <Link
          className="inline-flex min-h-11 items-center rounded-product px-3 text-sm font-semibold text-signal"
          href="/"
        >
          Back to workspace
        </Link>
      </div>
    </section>
  );
}
