"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, KeyRound } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card } from "@/components/ui";

export function Sources() {
  const { data } = useQuery({ queryKey: ["sources"], queryFn: api.sources });
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-ink">Sources</h1>
        <p className="mt-2 text-slate-600">Fixture mode works immediately. Real connectors stay behind credentials and API limits.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {(data ?? []).map((source) => (
          <Card key={source.id}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="rounded-lg bg-slate-100 p-2 text-signal"><Database size={18} /></span>
                <div>
                  <h2 className="font-semibold text-ink">{connectorName(source.type, source.name)}</h2>
                  <p className="mt-1 text-sm text-slate-600">{connectorCopy(source.type)}</p>
                </div>
              </div>
              <Badge tone={source.enabled ? "green" : "slate"}>{source.enabled ? "Enabled" : "Disabled"}</Badge>
            </div>
            <div className="mt-4 flex items-center gap-2 text-sm text-slate-600">
              <KeyRound size={16} />
              {credentialStatus(source.type)}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function connectorCopy(type: string) {
  const copy: Record<string, string> = {
    fixture: "Loads local JSON fixtures for a no-credential demo pipeline.",
    reddit: "Uses Reddit OAuth variables when configured.",
    hackernews: "Uses the public Hacker News API.",
    github: "Uses GitHub REST search, optionally with GITHUB_TOKEN.",
    stackexchange: "Uses Stack Exchange API, optionally with STACK_EXCHANGE_KEY."
  };
  return copy[type] ?? "Custom source connector.";
}

function connectorName(type: string, fallback: string) {
  const names: Record<string, string> = {
    fixture: "Fixture files",
    reddit: "Reddit API",
    hackernews: "Hacker News API",
    github: "GitHub Issues API",
    stackexchange: "Stack Exchange API"
  };
  return names[type] ?? fallback;
}

function credentialStatus(type: string) {
  if (type === "fixture" || type === "hackernews") return "No secret required for demo usage.";
  return "Credential optional or required for live scans. Not stored in the browser.";
}
