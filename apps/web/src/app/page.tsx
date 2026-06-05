import Link from "next/link";
import {
  ArrowRight,
  ClipboardCheck,
  FileText,
  Layers3,
  Search,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Badge, ButtonLink, Card, PageHeader } from "@/components/ui";

const examples = [
  {
    title: "AI-generated code needs production-readiness audits",
    source: "GitHub Issues",
    output: "Fixture opportunity",
  },
  {
    title: "Developers need clearer GitHub Actions failure diagnosis",
    source: "Hacker News",
    output: "Fixture opportunity",
  },
  {
    title: "Operators need spreadsheet-to-client-report automation",
    source: "Fixture data",
    output: "Fixture opportunity",
  },
];

const workflow = [
  {
    title: "Set the local workspace",
    description:
      "Store your research focus, default source, query, and cadence on this machine.",
    icon: Layers3,
  },
  {
    title: "Save and run projects",
    description:
      "Use public APIs by default, then add operator-gated credentials only when needed.",
    icon: ClipboardCheck,
  },
  {
    title: "Export a task pack",
    description:
      "Carry evidence, acceptance criteria, and privacy constraints into Codex or another agent.",
    icon: FileText,
  },
];

export default function LandingPage() {
  return (
    <AppShell>
      <div className="space-y-6 py-4">
        <PageHeader
          title="TaskSignal"
          description="A local-first research workbench for finding software opportunities from public complaints, reviewing the evidence, and handing focused tasks to Codex."
          actions={
            <>
              <ButtonLink href="/settings">Start setup</ButtonLink>
              <Link
                href="/dashboard"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-product border border-border bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
              >
                <Search size={16} /> Open dashboard
              </Link>
            </>
          }
        />

        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-muted">Start here</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">
                  Real local workflow
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
            <div className="mt-5 flex flex-wrap gap-2 border-t border-border pt-4">
              <Link
                href="/settings"
                className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
              >
                Configure workspace <ArrowRight size={15} />
              </Link>
              <Link
                href="/projects"
                className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
              >
                Save a project <ArrowRight size={15} />
              </Link>
            </div>
          </Card>

          <Card>
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
              <div>
                <p className="text-sm font-semibold text-muted">
                  Demo output
                </p>
                <h2 className="mt-1 text-xl font-semibold text-ink">
                  Fixture opportunities
                </h2>
              </div>
              <Badge tone="blue">Generated after processing fixtures</Badge>
            </div>
            <div className="mt-5 divide-y divide-border">
              {examples.map((example) => (
                <div
                  key={example.title}
                  className="grid gap-3 py-4 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_170px]"
                >
                  <div className="min-w-0">
                    <h3 className="break-words font-semibold text-ink">
                      {example.title}
                    </h3>
                    <p className="mt-1 text-sm text-muted">
                      Top source: {example.source}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 sm:justify-end">
                    <Badge>{example.output}</Badge>
                  </div>
                </div>
              ))}
            </div>
            <Link
              href="/dashboard"
              className="mt-5 inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
            >
              Open dashboard and review ranked evidence <ArrowRight size={15} />
            </Link>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
