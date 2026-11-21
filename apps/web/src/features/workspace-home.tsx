"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  FolderPlus,
  Play,
  RefreshCw,
  ScanLine,
} from "lucide-react";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { READINESS_TONES, reviewStateOption } from "@/lib/review";
import {
  DEFAULT_QUEUE_VIEW,
  queueHref,
  queueOpportunityHref,
  selectQueueItems,
} from "@/lib/queue-view";
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  PageHeader,
  StateMessage,
} from "@/components/ui";

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
    onSuccess: async () => {
      await Promise.all(
        [
          "stats",
          "opportunities",
          "scans",
          "readiness",
          "opportunity-threads",
          "sources",
          "evaluation",
        ].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
      );
    },
  });
  const hasEvidence = (stats.data?.total_items ?? 0) > 0;
  const queue = selectQueueItems(opportunities.data ?? [], DEFAULT_QUEUE_VIEW);
  const nextReview = queue.find((item) => item.review_state === "new");
  const error = stats.error ?? opportunities.error ?? projects.error;
  const loading =
    stats.isLoading || opportunities.isLoading || projects.isLoading;
  const attention = [
    ...queue.filter((item) => item.review_state === "new"),
    ...queue.filter((item) =>
      ["promising", "needs_more_evidence", "build_candidate"].includes(
        item.review_state,
      ),
    ),
  ].slice(0, 3);
  const recentProjects = [...(projects.data ?? [])]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 3);
  const emptyWorkspace =
    !loading && !error && !hasEvidence && queue.length === 0;
  const focusViews = [
    {
      state: "new" as const,
      label: "Needs a first look",
      description: "Read the source and decide what to explore.",
    },
    {
      state: "promising" as const,
      label: "Promising ideas",
      description: "Follow up on problems worth understanding.",
    },
    {
      state: "build_candidate" as const,
      label: "Build candidates",
      description: "Check evidence readiness before creating a packet.",
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Research overview"
        description="A clearer path from a real problem to your next build."
        actions={
          <>
            <Link
              href="/projects"
              className="inline-flex min-h-11 items-center gap-2 rounded-product px-3 text-sm font-semibold text-ink hover:bg-surface-muted"
            >
              <FolderPlus size={16} aria-hidden />
              New project
            </Link>
            <ButtonLink href="/dashboard">
              Open decision queue{" "}
              <ArrowRight size={16} className="ml-2" aria-hidden />
            </ButtonLink>
          </>
        }
      />

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
          Your queue now includes bundled fixture results. Open an idea to
          inspect its sources and practice a review.
        </StateMessage>
      ) : null}

      {emptyWorkspace || demo.isPending ? (
        <section className="onboarding-panel" aria-labelledby="first-run-title">
          <div>
            <ScanLine className="h-7 w-7 text-signal" aria-hidden />
            <h2
              id="first-run-title"
              className="mt-4 text-2xl font-semibold tracking-tight"
            >
              Start with a question worth answering.
            </h2>
            <p className="mt-3 max-w-lg text-sm leading-7 text-muted">
              Explore a complete research example, inspect the original
              evidence, and make your first decision. Or start a project around
              a problem you already care about.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Button loading={demo.isPending} onClick={() => demo.mutate()}>
                {demo.isPending ? (
                  <RefreshCw
                    size={16}
                    className="motion-safe:animate-spin"
                    aria-hidden
                  />
                ) : (
                  <Play size={16} aria-hidden />
                )}
                {demo.isPending ? "Preparing demo…" : "Try demo data"}
              </Button>
              <Link
                href="/projects"
                className="inline-flex min-h-11 items-center gap-2 rounded-product px-3 text-sm font-semibold text-signal"
              >
                Create a project <ArrowRight size={16} aria-hidden />
              </Link>
            </div>
            <p className="mt-4 flex items-center gap-2 text-xs text-muted">
              <Check size={14} aria-hidden />
              Runs locally, with no API keys or paid model.
            </p>
          </div>
          <ol className="onboarding-steps">
            {[
              {
                title: "Collect",
                description:
                  "Gather public conversations around a recurring problem.",
              },
              {
                title: "Review",
                description:
                  "Read source evidence and record your own judgment.",
              },
              {
                title: "Build",
                description:
                  "Turn an eligible candidate into a verifiable build packet.",
              },
            ].map((step, index) => (
              <li key={step.title}>
                <span className="step-index">{index + 1}</span>
                <div>
                  <h3 className="font-semibold">{step.title}</h3>
                  <p className="mt-1 text-sm leading-6 text-muted">
                    {step.description}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section aria-label="Workspace overview" className="workspace-metrics">
        {[
          {
            label: "Evidence collected",
            value: stats.data?.total_items,
            hint: "Public source items",
            pending: stats.isLoading,
          },
          {
            label: "Problem signals",
            value: stats.data?.problem_signals,
            hint: "Tasks and pain points",
            pending: stats.isLoading,
          },
          {
            label: "Current opportunities",
            value: opportunities.data?.length,
            hint: "Latest snapshot per thread",
            pending: opportunities.isLoading,
          },
          {
            label: "Research projects",
            value: projects.data?.length,
            hint: "Repeatable research questions",
            pending: projects.isLoading,
          },
        ].map((metric) => (
          <div key={metric.label}>
            <p className="text-sm text-muted">{metric.label}</p>
            <p
              className="mt-2 text-3xl font-semibold tracking-tight tabular-nums"
              aria-busy={metric.pending}
            >
              {metric.value === undefined ? "—" : metric.value.toLocaleString()}
            </p>
            <p className="mt-1 text-xs leading-5 text-muted">{metric.hint}</p>
          </div>
        ))}
      </section>

      <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,1.7fr)_minmax(260px,1fr)]">
        <section aria-labelledby="review-title" className="min-w-0">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2
                id="review-title"
                className="text-xl font-semibold tracking-tight"
              >
                Ready for your attention
              </h2>
              <p className="mt-1 text-sm text-muted">
                Unreviewed ideas first, with the evidence close at hand.
              </p>
            </div>
            {nextReview && !opportunities.error ? (
              <Link
                href={queueOpportunityHref(nextReview.id, {
                  ...DEFAULT_QUEUE_VIEW,
                  review: "new",
                })}
                className="inline-flex min-h-11 items-center gap-2 whitespace-nowrap rounded-product text-sm font-semibold text-signal"
              >
                Review next <ArrowRight size={16} aria-hidden />
              </Link>
            ) : null}
          </div>
          {loading || demo.isPending ? (
            <div role="status" className="space-y-4">
              <span className="sr-only">Loading research overview</span>
              {[0, 1, 2].map((item) => (
                <div
                  key={item}
                  className="h-24 rounded-product bg-surface-muted motion-safe:animate-pulse"
                />
              ))}
            </div>
          ) : null}
          {!loading &&
          !demo.isPending &&
          !opportunities.error &&
          attention.length === 0 ? (
            <Card variant="muted" className="py-8">
              <h3 className="font-semibold">
                {queue.length
                  ? "Your first-pass reviews are complete."
                  : "Your next idea starts with evidence."}
              </h3>
              <p className="mt-2 max-w-md text-sm leading-6 text-muted">
                {queue.length
                  ? "Revisit a previous decision in the queue, or collect fresh evidence from a research project."
                  : "Run the demo above or create a project. Your current opportunities will appear here."}
              </p>
              <Link
                href={queue.length ? "/dashboard" : "/projects"}
                className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-product text-sm font-semibold text-signal"
              >
                {queue.length
                  ? "View all decisions"
                  : "Create your first project"}
                <ArrowRight size={16} aria-hidden />
              </Link>
            </Card>
          ) : null}
          {!loading && !demo.isPending && attention.length > 0 ? (
            <div className="attention-list">
              {attention.map((item) => {
                const state = reviewStateOption(item.review_state);
                return (
                  <Link
                    key={item.id}
                    href={queueOpportunityHref(item.id, DEFAULT_QUEUE_VIEW)}
                    className="attention-item group"
                  >
                    <div className="min-w-0">
                      <div className="mb-3 flex flex-wrap items-center gap-2">
                        <Badge tone={state.tone}>{state.label}</Badge>
                        <span className="text-xs text-muted">
                          {item.evidence_readiness.evidence_count} evidence
                          items
                        </span>
                      </div>
                      <h3 className="text-base font-semibold leading-6 group-hover:text-signal">
                        {item.title}
                      </h3>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
                        {item.problem_statement}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <Badge
                          tone={READINESS_TONES[item.evidence_readiness.level]}
                        >
                          {item.evidence_readiness.level} evidence
                        </Badge>
                        <span className="text-xs text-muted">
                          {item.evidence_readiness.reviewed_count} reviewed ·{" "}
                          {item.top_source}
                        </span>
                      </div>
                    </div>
                    <ArrowRight
                      size={18}
                      className="mt-1 shrink-0 text-muted group-hover:text-signal"
                      aria-hidden
                    />
                  </Link>
                );
              })}
            </div>
          ) : null}
          {!loading && !opportunities.error && queue.length > 0 ? (
            <p className="mt-4 text-xs leading-6 text-muted">
              Scores help you prioritize. Reading the evidence and validating
              the problem are still your decisions.
            </p>
          ) : null}
        </section>

        <div className="space-y-8">
          <section aria-labelledby="focus-title">
            <h2
              id="focus-title"
              className="text-xl font-semibold tracking-tight"
            >
              Pick up where you left off
            </h2>
            <div className="mt-3 divide-y divide-border">
              {focusViews.map((view) => (
                <Link
                  key={view.state}
                  href={queueHref({
                    ...DEFAULT_QUEUE_VIEW,
                    review: view.state,
                  })}
                  className="focus-view group"
                >
                  <div>
                    <h3 className="text-sm font-semibold group-hover:text-signal">
                      {view.label}
                    </h3>
                    <p className="mt-1 text-xs leading-5 text-muted">
                      {view.description}
                    </p>
                  </div>
                  <span className="text-xl font-semibold tabular-nums text-signal">
                    {opportunities.data
                      ? queue.filter((item) => item.review_state === view.state)
                          .length
                      : "—"}
                  </span>
                </Link>
              ))}
            </div>
          </section>
          <section
            aria-labelledby="projects-title"
            className="min-w-0 border-t border-border pt-6"
          >
            <h2
              id="projects-title"
              className="text-xl font-semibold tracking-tight"
            >
              Research projects
            </h2>
            {projects.isLoading ? (
              <div
                aria-hidden
                className="mt-4 h-20 rounded-product bg-surface-muted motion-safe:animate-pulse"
              />
            ) : projects.error ? (
              <p className="mt-3 text-sm leading-6 text-muted">
                Project details are temporarily unavailable.
              </p>
            ) : recentProjects.length ? (
              <div className="mt-3 divide-y divide-border">
                {recentProjects.map((project) => (
                  <Link
                    key={project.id}
                    href={`/projects/${project.id}`}
                    className="group block rounded-product py-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="min-w-0 truncate text-sm font-semibold group-hover:text-signal">
                        {project.name}
                      </h3>
                      <ArrowRight
                        size={15}
                        className="shrink-0 text-muted"
                        aria-hidden
                      />
                    </div>
                    <p className="mt-1 line-clamp-1 text-xs leading-5 text-muted">
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
              <p className="mt-3 text-sm leading-6 text-muted">
                Save a research question and compare what changes on each run.
              </p>
            )}
            {!projects.isLoading ? (
              <Link
                href="/projects"
                className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-product text-sm font-semibold text-signal"
              >
                <FolderPlus size={16} aria-hidden />
                {projects.error
                  ? "View projects"
                  : recentProjects.length
                    ? "Manage projects"
                    : "Create a research project"}
              </Link>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
