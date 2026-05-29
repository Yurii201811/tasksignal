import Link from "next/link";
import { ArrowRight, ClipboardCheck, Layers3, Sparkles } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Badge, ButtonLink, Card } from "@/components/ui";

const examples = [
  "AI-generated code needs production-readiness audits",
  "Developers need clearer GitHub Actions failure diagnosis",
  "Operators need spreadsheet-to-client-report automation"
];

export default function LandingPage() {
  return (
    <AppShell>
      <div className="grid gap-8 py-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
        <section className="space-y-7">
          <div className="space-y-5">
            <h1 className="max-w-4xl text-4xl font-semibold leading-tight tracking-normal text-ink sm:text-6xl">
              Find real software ideas from public complaints and repetitive workflows.
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-600">
              TaskSignal turns Reddit, Hacker News, GitHub Issues, Stack Exchange, and fixture data into evidence-backed project opportunities and Codex-ready MVP prompts.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <ButtonLink href="/dashboard">Open dashboard</ButtonLink>
            <Link href="/search" className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-slate-50">
              Try semantic search <ArrowRight size={16} />
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card>
              <Layers3 className="mb-3 text-signal" size={22} />
              <h2 className="text-sm font-semibold text-ink">Cluster evidence-backed problems</h2>
              <p className="mt-2 text-sm text-slate-600">DBSCAN grouping with deterministic fallback for local demos.</p>
            </Card>
            <Card>
              <ClipboardCheck className="mb-3 text-amberline" size={22} />
              <h2 className="text-sm font-semibold text-ink">Score real workflow pain</h2>
              <p className="mt-2 text-sm text-slate-600">Prioritizes concrete repeated tasks over vague complaints.</p>
            </Card>
            <Card>
              <Sparkles className="mb-3 text-sky-600" size={22} />
              <h2 className="text-sm font-semibold text-ink">Export Codex-ready prompts</h2>
              <p className="mt-2 text-sm text-slate-600">Template generation works with no paid LLM API.</p>
            </Card>
          </div>
        </section>
        <Card className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-500">Example opportunities</p>
              <h2 className="text-2xl font-semibold text-ink">Fixture demo output</h2>
            </div>
            <Badge tone="green">Local-first</Badge>
          </div>
          <div className="space-y-3">
            {examples.map((example, index) => (
              <div key={example} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-4">
                  <h3 className="font-semibold text-ink">{example}</h3>
                  <span className="text-sm font-semibold text-signal">{88 - index * 7}%</span>
                </div>
                <p className="mt-2 text-sm text-slate-600">
                  Evidence from public discussion fixtures, scored for pain, frequency, buying intent, and feasibility.
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

