"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, KeyRound, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { Badge, Button, Card, PageHeader, StateMessage } from "@/components/ui";
import { DiscourseSourceManager } from "@/features/discourse-source-manager";

export function Sources() {
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.sources });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sources"
        description="Fixture mode works immediately. Live connectors remain explicit about credentials, public APIs, and rate limits."
      />

      {sources.error ? (
        <StateMessage
          tone="danger"
          title="Could not load sources"
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void sources.refetch()}
              loading={sources.isFetching}
              disabled={sources.isFetching}
            >
              <RefreshCw
                size={15}
                aria-hidden
                className={
                  sources.isFetching ? "motion-safe:animate-spin" : undefined
                }
              />
              {sources.isFetching ? "Retrying" : "Retry"}
            </Button>
          }
        >
          {apiErrorMessage(sources.error)}{" "}
          {sources.data
            ? "The last loaded registry stays below until a retry succeeds."
            : "Check that the local API is running, then retry."}
        </StateMessage>
      ) : null}

      {sources.isLoading ? (
        <StateMessage tone="info" title="Loading source registry">
          Checking fixture and live connector availability.
        </StateMessage>
      ) : null}

      {sources.isSuccess && sources.data.length === 0 ? (
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

      <DiscourseSourceManager
        sources={(sources.data ?? []).filter(
          (source) => source.type === "discourse",
        )}
      />
    </div>
  );
}

function connectorCopy(type: string) {
  const copy: Record<string, string> = {
    fixture: "Loads local JSON fixtures for a no-credential demo pipeline.",
    reddit: "Uses Reddit OAuth variables when configured on the backend.",
    hackernews: "Uses the public Hacker News API.",
    github:
      "Uses GitHub REST search, optionally with GITHUB_TOKEN on the backend.",
    stackexchange:
      "Uses the Stack Exchange API, optionally with STACK_EXCHANGE_KEY on the backend.",
    discourse:
      "Reads bounded public topic search results from one explicitly authorized HTTPS forum.",
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
  // Discourse forums are operator-named and there can be several, so their
  // own display name must stay visible instead of a shared connector label.
  if (type === "discourse") return fallback.trim() || "Discourse forum";
  return names[type] ?? fallback;
}

function credentialStatus(type: string) {
  if (type === "fixture" || type === "hackernews") {
    return "No secret required for demo usage.";
  }
  if (type === "discourse") {
    return "No source credentials or cookies are accepted. Exact host terms confirmation is required.";
  }
  return "Credential optional or required for live scans. Secrets are backend environment variables, not browser storage.";
}
