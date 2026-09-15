"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ArrowLeft } from "lucide-react";
import { parseQueueView, queueHref } from "@/lib/queue-view";

const linkStyle =
  "inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)]";

function ReturnLink() {
  const searchParams = useSearchParams();
  const context = searchParams.get("queue");
  // Only known queue fields are accepted; no arbitrary redirect destination.
  const href = queueHref(parseQueueView(new URLSearchParams(context ?? "")));
  return (
    <Link href={href} className={linkStyle}>
      <ArrowLeft size={16} aria-hidden />
      {context ? "Back to filtered queue" : "Back to decision queue"}
    </Link>
  );
}

export function QueueReturnLink() {
  return (
    <Suspense
      fallback={
        <Link href="/dashboard" className={linkStyle}>
          Back to decision queue
        </Link>
      }
    >
      <ReturnLink />
    </Suspense>
  );
}
