"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  Clipboard,
  RefreshCw,
  SearchIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import type { SemanticSearch as SemanticSearchResults } from "@/lib/types";
import { safeExternalUrl } from "@/lib/url";
import {
  Badge,
  Button,
  Card,
  Input,
  PageHeader,
  StateMessage,
} from "@/components/ui";

const DEFAULT_QUERY = "weekly spreadsheet client report";
const EMPTY_STATE_QUERY = "support ticket triage";

type SearchStatus = "idle" | "pending" | "success" | "error";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function SemanticSearch() {
  const searchParams = useSearchParams();
  const locationQuery = searchParams.get("q")?.trim() ?? "";
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [resultsQuery, setResultsQuery] = useState("");
  const [results, setResults] = useState<SemanticSearchResults | null>(null);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [error, setError] = useState<unknown>(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const latestRequest = useRef(0);
  const handledLocationQuery = useRef<string | null>(null);
  const copyResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const trimmedQuery = query.trim();
  const isPending = status === "pending";
  const evidenceCount = results?.evidence_hits.length ?? 0;
  const threadCount = results?.opportunity_threads.length ?? 0;
  const resultCount = evidenceCount + threadCount;
  const hasResults = resultCount > 0;

  const runSearch = useCallback(
    async (nextQuery: string, updateUrl: boolean) => {
      const normalizedQuery = nextQuery.trim();
      if (!normalizedQuery) return;

      const requestId = ++latestRequest.current;
      setSubmittedQuery(normalizedQuery);
      setStatus("pending");
      setError(null);
      setLinkCopied(false);

      if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set("q", normalizedQuery);
        handledLocationQuery.current = normalizedQuery;
        window.history.pushState({}, "", url);
      }

      try {
        const nextResults = await api.semanticSearch(normalizedQuery);
        if (requestId !== latestRequest.current) return;
        setResults(nextResults);
        setResultsQuery(normalizedQuery);
        setStatus("success");
      } catch (nextError) {
        if (requestId !== latestRequest.current) return;
        setError(nextError);
        setStatus("error");
      }
    },
    [],
  );

  useEffect(() => {
    if (handledLocationQuery.current === locationQuery) return;
    handledLocationQuery.current = locationQuery;
    latestRequest.current += 1;
    setQuery(locationQuery || DEFAULT_QUERY);
    setLinkCopied(false);

    if (locationQuery) {
      void runSearch(locationQuery, false);
    } else {
      setSubmittedQuery("");
      setResultsQuery("");
      setResults(null);
      setError(null);
      setStatus("idle");
    }
  }, [locationQuery, runSearch]);

  useEffect(
    () => () => {
      if (copyResetTimer.current) clearTimeout(copyResetTimer.current);
    },
    [],
  );

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runSearch(trimmedQuery, true);
  }

  function tryExample() {
    setQuery(EMPTY_STATE_QUERY);
    void runSearch(EMPTY_STATE_QUERY, true);
  }

  async function copySearchLink() {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("q", resultsQuery);
      await navigator.clipboard.writeText(url.toString());
      setLinkCopied(true);
      if (copyResetTimer.current) clearTimeout(copyResetTimer.current);
      copyResetTimer.current = setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      setLinkCopied(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Semantic search"
        description="Find evidence and opportunity threads by describing the workflow, pain point, or recurring job you want to investigate."
      />

      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <div className="min-w-0 flex-1">
            <label
              htmlFor="semantic-search-query"
              className="mb-2 block text-sm font-semibold text-ink"
            >
              Search the evidence library
            </label>
            <Input
              id="semantic-search-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Describe a repetitive workflow"
              aria-describedby="semantic-search-help"
              autoComplete="off"
            />
          </div>
          <Button
            type="submit"
            disabled={!trimmedQuery || isPending}
            loading={isPending}
            className="sm:mt-7 sm:self-start"
          >
            {isPending ? (
              <RefreshCw
                className="motion-safe:animate-spin"
                size={16}
                aria-hidden
              />
            ) : (
              <SearchIcon size={16} aria-hidden />
            )}
            {isPending ? "Searching" : "Search evidence"}
          </Button>
        </form>
        <p
          id="semantic-search-help"
          className="mt-3 text-xs leading-5 text-muted"
        >
          Press Enter to search. Your submitted query is saved in the page URL
          so you can share or revisit it. Similarity is a retrieval score, not a
          validation claim.
        </p>
      </Card>

      {status === "error" ? (
        <StateMessage
          tone="danger"
          title="Search did not complete"
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void runSearch(submittedQuery, false)}
            >
              <RefreshCw size={15} aria-hidden /> Retry search
            </Button>
          }
        >
          {errorMessage(error)}
          {results
            ? " Existing results remain available below."
            : " Check that the local API is running, then retry."}
        </StateMessage>
      ) : null}
      {isPending ? (
        <StateMessage
          tone="info"
          title={
            results ? "Updating search results" : "Searching local evidence"
          }
        >
          {results
            ? `Keeping the previous results visible while searching for “${submittedQuery}”.`
            : "Ranking normalized items by embedding similarity."}
        </StateMessage>
      ) : null}
      {status === "success" && !hasResults ? (
        <StateMessage
          tone="warning"
          title={`No results for “${submittedQuery}”`}
          action={
            <Button variant="secondary" size="sm" onClick={tryExample}>
              <SearchIcon size={15} aria-hidden /> Try a broader example
            </Button>
          }
        >
          Use a shorter workflow phrase, remove product names, or process demo
          data from the dashboard first.
        </StateMessage>
      ) : null}

      {hasResults ? (
        <div className="space-y-6" aria-live="polite" aria-busy={isPending}>
          <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-ink">
                {resultCount} {resultCount === 1 ? "result" : "results"} for “
                {resultsQuery}”
              </h2>
              <p className="mt-1 text-sm text-muted">
                {evidenceCount} evidence {evidenceCount === 1 ? "hit" : "hits"}
                {" · "}
                {threadCount} opportunity{" "}
                {threadCount === 1 ? "thread" : "threads"}
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={copySearchLink}>
              {linkCopied ? (
                <Check size={15} aria-hidden />
              ) : (
                <Clipboard size={15} aria-hidden />
              )}
              {linkCopied ? "Link copied" : "Copy search link"}
            </Button>
          </div>

          {evidenceCount > 0 ? (
            <section
              className="space-y-3"
              aria-labelledby="evidence-results-heading"
            >
              <div className="flex items-baseline justify-between gap-3">
                <h2
                  id="evidence-results-heading"
                  className="text-lg font-semibold text-ink"
                >
                  Evidence hits
                </h2>
                <span className="text-xs font-semibold text-muted">
                  {evidenceCount} ranked by similarity
                </span>
              </div>
              <ol className="grid gap-4">
                {(results?.evidence_hits ?? []).map((result, index) => {
                  const sourceUrl = safeExternalUrl(result.source_url);
                  return (
                    <li key={result.id}>
                      <Card className="h-full">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-semibold text-muted">
                            {index + 1}.
                          </span>
                          <Badge tone="blue">{result.source}</Badge>
                          {result.signal_type ? (
                            <Badge tone="green">
                              {result.signal_type.replaceAll("_", " ")}
                            </Badge>
                          ) : null}
                          <Badge>
                            Match {Math.round(result.match_score * 100)}%
                          </Badge>
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
                    </li>
                  );
                })}
              </ol>
            </section>
          ) : null}

          {threadCount > 0 ? (
            <section
              className="space-y-3"
              aria-labelledby="thread-results-heading"
            >
              <div className="flex items-baseline justify-between gap-3">
                <h2
                  id="thread-results-heading"
                  className="text-lg font-semibold text-ink"
                >
                  Related opportunity threads
                </h2>
                <span className="text-xs font-semibold text-muted">
                  {threadCount} grouped from matched evidence
                </span>
              </div>
              <ol className="grid gap-4 lg:grid-cols-2">
                {(results?.opportunity_threads ?? []).map((result) => (
                  <li key={result.id}>
                    <Card className="flex h-full flex-col">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="blue">
                          Match {Math.round(result.match_score * 100)}%
                        </Badge>
                        <Badge>
                          {result.review_state.replaceAll("_", " ")}
                        </Badge>
                        <Badge>
                          {result.evidence_readiness.level} readiness
                        </Badge>
                      </div>
                      <h3 className="mt-3 break-words font-semibold text-ink">
                        {result.title}
                      </h3>
                      <p className="mt-2 break-words text-sm leading-6 text-muted">
                        {result.summary}
                      </p>
                      <p className="mt-3 text-xs font-semibold text-muted">
                        {result.matched_evidence_count} matched evidence{" "}
                        {result.matched_evidence_count === 1
                          ? "record"
                          : "records"}
                      </p>
                      <Link
                        href={`/threads/${result.id}`}
                        className="mt-auto inline-flex min-h-11 items-center gap-2 self-start rounded-product pt-3 text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
                      >
                        Open opportunity thread{" "}
                        <ArrowRight size={15} aria-hidden />
                      </Link>
                    </Card>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
