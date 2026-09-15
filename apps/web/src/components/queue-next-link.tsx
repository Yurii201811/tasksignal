"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import {
  parseQueueView,
  queueOpportunityHref,
  selectQueueItems,
} from "@/lib/queue-view";
import { Button } from "./ui";

function NextLink({ currentId, dirty }: { currentId: string; dirty: boolean }) {
  const params = useSearchParams();
  const context = params.get("queue");
  const view = parseQueueView(new URLSearchParams(context ?? ""));
  const [neighbor, setNeighbor] = useState<{
    currentId: string;
    context: string | null;
    nextId: string | null;
  } | null>(null);
  const queue = useQuery({
    queryKey: ["opportunities", "review-navigation", context],
    enabled: context !== null,
    queryFn: () =>
      api.opportunities({
        currentOnly: true,
        ...(view.project !== "all" ? { projectId: view.project } : {}),
        ...(view.source !== "all" ? { evidenceSource: view.source } : {}),
        ...(view.readiness !== "all" ? { readiness: view.readiness } : {}),
        ...(view.age !== "all" ? { maxAgeDays: Number(view.age) } : {}),
        ...(view.review !== "all" ? { reviewState: view.review } : {}),
      }),
  });
  useEffect(() => {
    if (
      !queue.data ||
      (neighbor?.currentId === currentId && neighbor.context === context)
    )
      return;
    const rows = selectQueueItems(
      queue.data,
      parseQueueView(new URLSearchParams(context ?? "")),
    );
    const index = rows.findIndex((item) => item.id === currentId);
    setNeighbor({
      currentId,
      context,
      nextId: index < 0 ? null : (rows[index + 1]?.id ?? null),
    });
  }, [context, currentId, neighbor, queue.data]);
  if (context === null) return null;
  const nextId =
    neighbor?.currentId === currentId && neighbor.context === context
      ? neighbor.nextId
      : null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
      <p className="text-xs leading-6 text-muted">
        {dirty
          ? "Save your review changes before moving to the next idea."
          : queue.error
            ? "Next idea unavailable. Return to your queue to retry."
            : queue.isLoading
              ? "Finding the next idea in this view…"
              : nextId
                ? "Continue in your original queue order. Nothing is saved automatically."
                : "You have reached the end of this queue view."}
      </p>
      {nextId && !dirty && !queue.error ? (
        <Link
          href={queueOpportunityHref(nextId, view)}
          className="inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-product text-sm font-semibold text-signal"
        >
          Next in this queue <ArrowRight size={16} aria-hidden />
        </Link>
      ) : dirty ? (
        <Button disabled variant="secondary">
          Next in this queue
        </Button>
      ) : null}
    </div>
  );
}

export function QueueNextLink(props: { currentId: string; dirty: boolean }) {
  return (
    <Suspense fallback={null}>
      <NextLink {...props} />
    </Suspense>
  );
}
