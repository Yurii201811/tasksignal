"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, Copy, Download } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card, PageHeader, StateMessage } from "@/components/ui";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request failed.";
}

export function PromptView({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const { data, error, isError, isLoading } = useQuery({
    queryKey: ["prompt", id],
    queryFn: () => api.prompt(id),
  });
  const prompt = data?.prompt ?? "";
  const canCopy = Boolean(prompt) && !isLoading;

  async function copyPrompt() {
    if (!canCopy) return;
    try {
      await navigator.clipboard.writeText(prompt);
      setCopyError(null);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch (clipboardError) {
      setCopyError(errorMessage(clipboardError));
    }
  }

  return (
    <div className="space-y-6">
      <Link
        href={`/opportunities/${id}`}
        className="inline-flex min-h-9 items-center gap-1 rounded-product text-sm font-semibold text-signal hover:text-[var(--ts-accent-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
      >
        <ArrowLeft size={15} /> Back to evidence
      </Link>

      <PageHeader
        title="Generated Codex Prompt"
        description="Copy or download the prompt with evidence excerpts, ranking rationale, and privacy constraints intact."
        actions={
          <>
            <Button onClick={copyPrompt} disabled={!canCopy} variant="primary">
              <Copy size={16} /> {copied ? "Copied" : "Copy prompt"}
            </Button>
            <a
              href={api.exportUrl(id)}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-product border border-border bg-surface px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
            >
              <Download size={16} /> Download .md
            </a>
          </>
        }
      />

      {copyError ? (
        <StateMessage tone="danger" title="Copy did not complete">
          {copyError}
        </StateMessage>
      ) : null}
      {copied ? (
        <StateMessage tone="success" title="Prompt copied">
          The clipboard now contains the exact generated prompt text.
        </StateMessage>
      ) : null}
      {isLoading ? (
        <StateMessage tone="info" title="Loading generated prompt">
          Fetching the Markdown preview from the local API.
        </StateMessage>
      ) : null}
      {isError ? (
        <StateMessage tone="danger" title="Could not load generated prompt">
          {errorMessage(error)}
        </StateMessage>
      ) : null}

      {!isLoading && !isError && (
        <Card className="prose max-w-none break-words prose-pre:whitespace-pre-wrap prose-pre:break-words prose-code:break-words">
          {prompt ? (
            <ReactMarkdown>{prompt}</ReactMarkdown>
          ) : (
            <p>Process demo data first, then open a generated opportunity prompt.</p>
          )}
        </Card>
      )}
    </div>
  );
}
