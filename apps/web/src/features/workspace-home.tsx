"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  FileCheck2,
  FolderPlus,
  GitBranch,
  Play,
  RefreshCw,
  ScanLine,
} from "lucide-react";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { reviewStateOption } from "@/lib/review";
import { Badge, Button, ButtonLink, Card, StateMessage } from "@/components/ui";

const steps = [
  {
    title: "Collect the signals",
    description: "Save a research question. Gather public evidence.",
    href: "/projects",
    icon: ScanLine,
  },
  {
    title: "Make a decision",
    description: "Review the source, the score, and what is still missing.",
    href: "/dashboard",
    icon: GitBranch,
  },
  {
    title: "Build with context",
    description: "Turn a reviewed thread into a verifiable build packet.",
    href: "/threads",
    icon: FileCheck2,
  },
];

export function WorkspaceHome() {
  const queryClient = useQueryClient();
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const opportunities = useQuery({
    queryKey: ["opportunities", "all"],
    queryFn: () => api.opportunities({ currentOnly: true }),
  });
  const projects = useQuery({
    queryKey: ["research-projects"],
    queryFn: api.researchProjects,
  });
  const demo = useMutation({
    mutationFn: api.processDemo,
    onSuccess: () => {
      for (const key of [
        "stats",
        "opportunities",
        "scans",
        "readiness",
        "opportunity-threads",
        "sources",
      ]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
  });
  const hasEvidence = (stats.data?.total_items ?? 0) > 0;
  const queue = opportunities.data ?? [];
  const nextReview = queue.find((item) => item.review_state === "new");
  const error = stats.error ?? opportunities.error ?? projects.error;
  const loading =
    stats.isLoading || opportunities.isLoading || projects.isLoading;
  const recentProjects = [...(projects.data ?? [])]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 3);

  return (
    <div className="space-y-8">
      <section
        className="home-hero grid gap-10 overflow-hidden rounded-2xl border border-border p-6 sm:p-9 xl:grid-cols-[1.25fr_1fr] xl:items-center xl:gap-16"
        aria-labelledby="welcome-title"
      >
        <div>
          <p className="eyebrow flex items-center gap-2 text-signal">
            <span className="h-1.5 w-1.5 rounded-full bg-signal" /> Your
            research workspace
          </p>
          <h1
            id="welcome-title"
            className="mt-5 max-w-xl text-4xl font-semibold leading-[1.12] tracking-[-0.045em] text-ink sm:text-5xl"
          >
            Good software starts with a real problem.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-7 text-muted">
            Find the signals in public conversations. Follow the evidence.
            Decide what deserves to be built.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <ButtonLink href="/dashboard">
              Open decision queue{" "}
              <ArrowRight className="ml-2 h-4 w-4" aria-hidden />
            </ButtonLink>
            {!loading && !error && !hasEvidence ? (
              <Button
                variant="secondary"
                onClick={() => demo.mutate()}
                loading={demo.isPending}
              >
                {demo.isPending ? (
                  <RefreshCw
                    className="h-4 w-4 motion-safe:animate-spin"
                    aria-hidden
                  />
                ) : (
                  <Play className="h-4 w-4" aria-hidden />
                )}
                {demo.isPending ? "Preparing demo…" : "Try demo data"}
              </Button>
            ) : !loading ? (
              <Link
                href="/projects"
                className="inline-flex min-h-11 items-center gap-2 rounded-product px-3 text-sm font-semibold text-ink hover:bg-surface-muted"
              >
                New research project{" "}
                <FolderPlus className="h-4 w-4" aria-hidden />
              </Link>
            ) : null}
          </div>
          <p className="mt-5 flex items-center gap-2 text-xs text-muted">
            <Check className="h-3.5 w-3.5 text-signal" aria-hidden /> Demo runs
            locally. No API keys or paid model required.
          </p>
        </div>
        <ol className="divide-y divide-border border-y border-border">
          {steps.map((step, index) => (
            <li key={step.title}>
              <Link
                href={step.href}
                className="group flex items-start gap-4 rounded-product px-2 py-6 hover:bg-surface-muted"
              >
                <span className="mt-1 font-mono text-xs tabular-nums text-muted">
                  0{index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-base font-semibold tracking-tight">
                    {step.title}
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-muted">
                    {step.description}
                  </p>
                </div>
                <step.icon
                  className="mt-1 h-5 w-5 shrink-0 text-signal"
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ol>
      </section>

      {error ? (
        <StateMessage
          tone="danger"
          title="Could not load your workspace"
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void stats.refetch();
                void opportunities.refetch();
                void projects.refetch();
              }}
            >
              Try again
            </Button>
          }
        >
          {apiErrorMessage(error)}
        </StateMessage>
      ) : null}
      {demo.error ? (
        <StateMessage tone="danger" title="Could not prepare demo data">
          {apiErrorMessage(demo.error)}
        </StateMessage>
      ) : null}
      {demo.isSuccess ? (
        <StateMessage tone="success" title="Demo evidence is ready">
          Open the decision queue to review the generated opportunities. These
          results come from bundled fixtures.
        </StateMessage>
      ) : null}

      <section
        aria-label="Workspace overview"
        className="grid grid-cols-2 gap-x-6 gap-y-5 border-b border-border px-1 pb-7 lg:grid-cols-4"
      >
        {[
          {
            label: "Evidence collected",
            value: stats.data?.total_items,
            hint: "Source items in this workspace",
          },
          {
            label: "Problem signals",
            value: stats.data?.problem_signals,
            hint: "Detected tasks and pain points",
          },
          {
            label: "Current opportunities",
            value: opportunities.data?.length,
            hint: "Latest snapshots to consider",
          },
          {
            label: "Research projects",
            value: projects.data?.length,
            hint: "Repeatable research questions",
          },
        ].map((metric) => (
          <div key={metric.label}>
            <p className="text-sm text-muted">{metric.label}</p>
            <p
              className="mt-2 text-3xl font-semibold tracking-tight tabular-nums"
              aria-busy={loading}
            >
              {metric.value === undefined ? "—" : metric.value.toLocaleString()}
            </p>
            <p className="mt-1 text-xs leading-5 text-muted">{metric.hint}</p>
          </div>
        ))}
      </section>

      <div className="grid items-start gap-8 xl:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="review-title" className="min-w-0">
          <div className="mb-5 flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow text-muted">Make progress</p>
              <h2
                id="review-title"
                className="mt-1 text-xl font-semibold tracking-tight"
              >
                Ready for your attention
              </h2>
            </div>
            <Link
              href="/dashboard"
              className="inline-flex min-h-11 items-center gap-1 rounded-product px-2 text-sm font-semibold text-signal"
            >
              View all <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          </div>
          {loading ? (
            <div role="status" className="space-y-4">
              <span className="sr-only">Loading research overview</span>
              {[0, 1, 2].map((item) => (
                <div
                  key={item}
                  className="h-20 rounded-product bg-surface-muted motion-safe:animate-pulse"
                />
              ))}
            </div>
          ) : null}
          {!loading && !opportunities.error && queue.length === 0 ? (
            <Card className="py-8">
              <ScanLine className="h-7 w-7 text-signal" aria-hidden />
              <h3 className="mt-4 font-semibold">
                Start with a question worth answering.
              </h3>
              <p className="mt-2 max-w-md text-sm leading-6 text-muted">
                Run the demo to explore a complete example, or create a project
                around a problem you want to understand.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Link
                  href="/projects"
                  className="inline-flex min-h-11 items-center px-3 text-sm font-semibold text-signal"
                >
                  Create a project{" "}
                  <ArrowRight className="ml-2 h-4 w-4" aria-hidden />
                </Link>
              </div>
            </Card>
          ) : null}
          {!loading && queue.length > 0 ? (
            <div className="divide-y divide-border rounded-xl border border-border bg-surface">
              {(nextReview
                ? [
                    nextReview,
                    ...queue.filter((item) => item.id !== nextReview.id),
                  ]
                : queue
              )
                .slice(0, 3)
                .map((item, index) => {
                  const state = reviewStateOption(item.review_state);
                  return (
                    <Link
                      key={item.id}
                      href={
                        item.thread_id
                          ? `/threads/${item.thread_id}`
                          : `/opportunities/${item.id}`
                      }
                      className="group flex items-start gap-4 px-5 py-5 first:rounded-t-xl last:rounded-b-xl hover:bg-surface-muted"
                    >
                      <span className="mt-1 font-mono text-xs text-muted">
                        0{index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-semibold leading-6 group-hover:text-signal">
                          {item.title}
                        </h3>
                        <p className="mt-1 line-clamp-2 text-sm leading-6 text-muted">
                          {item.problem_statement}
                        </p>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <Badge tone={state.tone}>{state.label}</Badge>
                          <span className="text-xs text-muted">
                            {item.top_source}
                          </span>
                        </div>
                      </div>
                      <ArrowRight
                        className="mt-1 h-4 w-4 shrink-0 text-muted group-hover:text-signal"
                        aria-hidden
                      />
                    </Link>
                  );
                })}
            </div>
          ) : null}
        </section>
        <section aria-labelledby="projects-title" className="min-w-0">
          <div className="mb-5">
            <p className="eyebrow text-muted">Keep exploring</p>
            <h2
              id="projects-title"
              className="mt-1 text-xl font-semibold tracking-tight"
            >
              Research projects
            </h2>
          </div>
          {projects.isLoading ? (
            <div
              aria-hidden="true"
              className="h-28 rounded-product bg-surface-muted motion-safe:animate-pulse"
            />
          ) : projects.error ? (
            <p className="text-sm leading-7 text-muted">
              Project details are temporarily unavailable.
            </p>
          ) : recentProjects.length > 0 ? (
            <div className="divide-y divide-border">
              {recentProjects.map((project) => (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="group block rounded-product py-4 first:pt-0"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="truncate font-semibold group-hover:text-signal">
                      {project.name}
                    </h3>
                    <ArrowRight
                      className="h-4 w-4 shrink-0 text-muted"
                      aria-hidden
                    />
                  </div>
                  <p className="mt-1 line-clamp-1 text-sm text-muted">
                    {project.query}
                  </p>
                  <p className="mt-2 text-xs text-muted">
                    {project.source_type} · {project.run_count}{" "}
                    {project.run_count === 1 ? "run" : "runs"}
                  </p>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-7 text-muted">
              Save your source, query, and research cadence once. Compare what
              changes on each run without losing the earlier evidence.
            </p>
          )}
          {!projects.isLoading ? (
            <Link
              href="/projects"
              className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-product text-sm font-semibold text-signal"
            >
              <FolderPlus className="h-4 w-4" aria-hidden />
              {projects.error
                ? "View projects"
                : recentProjects.length
                  ? "Manage projects"
                  : "Create your first project"}
            </Link>
          ) : null}
          <div className="mt-7 border-t border-border pt-5">
            <h3 className="text-sm font-semibold">
              Evidence first. Your judgment always.
            </h3>
            <p className="mt-2 text-sm leading-6 text-muted">
              Scores help prioritize research. Review the original sources
              before treating an opportunity as demand.
            </p>
            <Link
              href="/evaluation"
              className="mt-2 inline-flex min-h-11 items-center gap-1 rounded-product text-sm font-semibold text-signal"
            >
              Review evidence quality{" "}
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
