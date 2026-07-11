"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, RefreshCw, SearchIcon } from "lucide-react";
import { api } from "@/lib/api";
import { safeExternalUrl } from "@/lib/url";
import {
  Badge,
  Button,
  Card,
  Input,
  PageHeader,
  StateMessage,
} from "@/components/ui";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function SemanticSearch() {
  const [query, setQuery] = useState("weekly spreadsheet client report");
  const search = useMutation({ mutationFn: api.semanticSearch });
  const trimmedQuery = query.trim();
  const hasResults = Boolean(
    search.data &&
    (search.data.evidence_hits.length > 0 ||
      search.data.opportunity_threads.length > 0),
  );

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!trimmedQuery) return;
    search.mutate(trimmedQuery);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Semantic search"
        description="Search normalized evidence items using the same local embedding service as the clustering pipeline."
      />

      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <Input
            aria-label="Semantic search query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Describe a repetitive workflow"
          />
          <Button
            type="submit"
            disabled={!trimmedQuery || search.isPending}
            loading={search.isPending}
          >
            {search.isPending ? (
              <RefreshCw className="motion-safe:animate-spin" size={16} />
            ) : (
              <SearchIcon size={16} />
            )}
            {search.isPending ? "Searching" : "Search evidence"}
          </Button>
        </form>
        <p className="mt-3 text-xs leading-5 text-muted">
          Similarity is a computed retrieval score, not a validation claim.
        </p>
      </Card>

      {search.error ? (
        <StateMessage tone="danger" title="Search did not complete">
          {errorMessage(search.error)}
        </StateMessage>
      ) : null}
      {search.isPending ? (
        <StateMessage tone="info" title="Searching local evidence">
          Ranking normalized items by embedding similarity.
        </StateMessage>
      ) : null}
      {search.isSuccess && !hasResults ? (
        <StateMessage tone="warning" title="No matching evidence records">
          Try a more concrete workflow phrase, or process demo data from the
          dashboard first.
        </StateMessage>
      ) : null}

      {(search.data?.evidence_hits.length ?? 0) > 0 ? (
        <section
          className="space-y-3"
          aria-labelledby="evidence-results-heading"
        >
          <h2
            id="evidence-results-heading"
            className="text-lg font-semibold text-ink"
          >
            Evidence hits
          </h2>
          <div className="grid gap-4">
            {(search.data?.evidence_hits ?? []).map((result) => {
              const sourceUrl = safeExternalUrl(result.source_url);
              return (
                <Card key={result.id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="blue">{result.source}</Badge>
                    {result.signal_type ? (
                      <Badge tone="green">
                        {result.signal_type.replaceAll("_", " ")}
                      </Badge>
                    ) : null}
                    <Badge>Match {Math.round(result.match_score * 100)}%</Badge>
                  </div>
                  <h3 className="mt-3 break-words font-semibold text-ink">
                    {result.title || "Untitled evidence item"}
                  </h3>
                  <p className="mt-2 break-words text-sm leading-6 text-muted">
                    {result.excerpt}
                  </p>
                  {sourceUrl ? (
                    <a
                      href={sourceUrl}
                      className="mt-3 inline-flex min-h-11 items-center whitespace-nowrap rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)] motion-safe:active:translate-y-px"
                      rel="noreferrer"
                      target="_blank"
                    >
                      Open source
                    </a>
                  ) : null}
                </Card>
              );
            })}
          </div>
        </section>
      ) : null}

      {(search.data?.opportunity_threads.length ?? 0) > 0 ? (
        <section className="space-y-3" aria-labelledby="thread-results-heading">
          <h2
            id="thread-results-heading"
            className="text-lg font-semibold text-ink"
          >
            Related opportunity threads
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {(search.data?.opportunity_threads ?? []).map((result) => (
              <Card key={result.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="blue">
                    Match {Math.round(result.match_score * 100)}%
                  </Badge>
                  <Badge>{result.review_state.replaceAll("_", " ")}</Badge>
                  <Badge>{result.evidence_readiness.level} readiness</Badge>
                </div>
                <h3 className="mt-3 break-words font-semibold text-ink">
                  {result.title}
                </h3>
                <p className="mt-2 break-words text-sm leading-6 text-muted">
                  {result.summary}
                </p>
                <Link
                  href={`/threads/${result.id}`}
                  className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
                >
                  Open opportunity thread <ArrowRight size={15} aria-hidden />
                </Link>
              </Card>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
