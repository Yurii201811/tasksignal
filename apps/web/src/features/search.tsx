"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { RefreshCw, SearchIcon } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Card, Input, PageHeader, StateMessage } from "@/components/ui";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

type SearchItem = {
  title?: string;
  body?: string;
  source?: string;
  url?: string;
  signal_type?: string;
};

export function SemanticSearch() {
  const [query, setQuery] = useState("weekly spreadsheet client report");
  const search = useMutation({ mutationFn: api.semanticSearch });
  const trimmedQuery = query.trim();
  const hasResults = Boolean(search.data?.items.length);

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
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Describe a repetitive workflow"
          />
          <Button disabled={!trimmedQuery || search.isPending} loading={search.isPending}>
            {search.isPending ? (
              <RefreshCw className="animate-spin" size={16} />
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

      <div className="grid gap-4">
        {(search.data?.items ?? []).map((result, index) => {
          const item = result.item as SearchItem;
          const title = item.title || "Untitled evidence item";
          return (
            <Card key={`${title}-${index}`}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="blue">{item.source ?? "source"}</Badge>
                {item.signal_type ? (
                  <Badge tone="green">{item.signal_type.replace("_", " ")}</Badge>
                ) : null}
                <Badge>
                  Similarity {Math.round(result.similarity * 100)}
                </Badge>
              </div>
              <h2 className="mt-3 break-words font-semibold text-ink">{title}</h2>
              {item.body ? (
                <p className="mt-2 break-words text-sm leading-6 text-muted">
                  {item.body}
                </p>
              ) : null}
              {item.url ? (
                <a
                  href={item.url}
                  className="mt-3 inline-flex min-h-9 items-center rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
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
    </div>
  );
}
