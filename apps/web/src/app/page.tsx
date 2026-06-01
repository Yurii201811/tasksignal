import Link from "next/link";
import { ArrowRight, ClipboardCheck, FileText, Layers3, Search } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Badge, ButtonLink, Card, PageHeader } from "@/components/ui";

const examples = [
  {
    title: "AI-generated code needs production-readiness audits",
    score: 88,
    source: "GitHub Issues",
  },
  {
    title: "Developers need clearer GitHub Actions failure diagnosis",
    score: 81,
    source: "Hacker News",
  },
  {
    title: "Operators need spreadsheet-to-client-report automation",
    score: 74,
    source: "Fixture data",
  },
];

const workflow = [
  {
    title: "Process demo data",
    description: "Load local fixtures and generate ranked opportunities without credentials.",
    icon: Layers3,
  },
  {
    title: "Review the evidence",
    description: "Inspect source attribution, signal scores, and ranking drivers before trusting a result.",
    icon: ClipboardCheck,
  },
  {
    title: "Export a Codex prompt",
    description: "Carry the evidence trail into an MVP prompt without rewriting the source material.",
    icon: FileText,
  },
];

export default function LandingPage() {
  return (
    <AppShell>
      <div className="space-y-6 py-4">
        <PageHeader
          title="TaskSignal"
          description="A local-first workbench for finding software opportunities from public complaints, repetitive workflows, and fixture data."
          actions={
            <>
              <ButtonLink href="/dashboard">Open dashboard</ButtonLink>
              <Link
                href="/search"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-product border border-border bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
              >
                <Search size={16} /> Search evidence
              </Link>
            </>
          }
        />

        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-muted">Try first</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">
                  Evidence workflow
                </h2>
              </div>
              <Badge tone="green">No paid LLM required</Badge>
            </div>
            <div className="mt-5 grid gap-4">
              {workflow.map((step, index) => (
                <div key={step.title} className="flex gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-product bg-surface-muted text-signal">
                    <step.icon size={19} />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-ink">
                      {index + 1}. {step.title}
                    </p>
                    <p className="mt-1 text-sm leading-6 text-muted">
                      {step.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
              <div>
                <p className="text-sm font-semibold text-muted">
                  Fixture demo output
                </p>
                <h2 className="mt-1 text-xl font-semibold text-ink">
                  Ranked opportunities
                </h2>
              </div>
              <Badge tone="blue">Evidence-backed scores</Badge>
            </div>
            <div className="mt-5 divide-y divide-border">
              {examples.map((example) => (
                <div
                  key={example.title}
                  className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_72px]"
                >
                  <div className="min-w-0">
                    <h3 className="break-words font-semibold text-ink">
                      {example.title}
                    </h3>
                    <p className="mt-1 text-sm text-muted">
                      Top source: {example.source}
                    </p>
                  </div>
                  <div className="flex items-center justify-between gap-3 sm:block sm:text-right">
                    <span className="text-sm font-semibold text-muted">Score</span>
                    <span className="text-2xl font-semibold tabular-nums text-signal">
                      {example.score}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <Link
              href="/dashboard"
              className="mt-5 inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
            >
              Process fixtures and open the live dashboard <ArrowRight size={15} />
            </Link>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
