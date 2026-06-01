"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, KeyRound } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, PageHeader, StateMessage } from "@/components/ui";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function Sources() {
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sources"
        description="Fixture mode works immediately. Live connectors remain explicit about credentials, public APIs, and rate limits."
      />

      {sources.error ? (
        <StateMessage tone="danger" title="Could not load sources">
          {errorMessage(sources.error)}
        </StateMessage>
      ) : null}

      {sources.isLoading ? (
        <StateMessage tone="info" title="Loading source registry">
          Checking fixture and live connector availability.
        </StateMessage>
      ) : null}

      {!sources.isLoading && (sources.data ?? []).length === 0 ? (
        <StateMessage tone="warning" title="No sources are registered">
          Fixture data can still be processed if the backend has local fixture
          files available.
        </StateMessage>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {(sources.data ?? []).map((source) => (
          <Card key={source.id}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
              <div className="flex min-w-0 items-start gap-3">
                <span className="rounded-product bg-surface-muted p-2 text-signal">
                  <Database size={18} />
                </span>
                <div className="min-w-0">
                  <h2 className="break-words font-semibold text-ink">
                    {connectorName(source.type, source.name)}
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-muted">
                    {connectorCopy(source.type)}
                  </p>
                </div>
              </div>
              <div className="shrink-0">
                <Badge tone={source.enabled ? "green" : "slate"}>
                  {source.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>
            </div>
            <div className="mt-4 flex items-start gap-2 border-t border-border pt-4 text-sm leading-6 text-muted">
              <KeyRound className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{credentialStatus(source.type)}</span>
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
    reddit: "Uses Reddit OAuth variables when configured on the backend.",
    hackernews: "Uses the public Hacker News API.",
    github: "Uses GitHub REST search, optionally with GITHUB_TOKEN on the backend.",
    stackexchange:
      "Uses the Stack Exchange API, optionally with STACK_EXCHANGE_KEY on the backend.",
  };
  return copy[type] ?? "Custom source connector.";
}

function connectorName(type: string, fallback: string) {
  const names: Record<string, string> = {
    fixture: "Fixture files",
    reddit: "Reddit API",
    hackernews: "Hacker News API",
    github: "GitHub Issues API",
    stackexchange: "Stack Exchange API",
  };
  return names[type] ?? fallback;
}

function credentialStatus(type: string) {
  if (type === "fixture" || type === "hackernews") {
    return "No secret required for demo usage.";
  }
  return "Credential optional or required for live scans. Secrets are backend environment variables, not browser storage.";
}
