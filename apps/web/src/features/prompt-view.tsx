"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, Copy, Download } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Card, PageHeader, StateMessage } from "@/components/ui";

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
  const taskPackDownload = useMutation({
    mutationFn: () => api.downloadTaskPack(id),
  });
  const evidenceDownload = useMutation({
    mutationFn: () => api.downloadEvidence(id),
  });
  const promptDownload = useMutation({
    mutationFn: () => api.downloadPrompt(id),
  });
  const prompt = data?.prompt ?? "";
  const canCopy = Boolean(prompt) && !isLoading;
  const sectionCount = prompt ? (prompt.match(/^## /gm) ?? []).length : 0;
  const wordCount = prompt ? prompt.split(/\s+/).filter(Boolean).length : 0;
  const hasEvidence = prompt.includes("## Evidence");
  const hasRanking = prompt.includes("## Ranking rationale");
  const hasPrivacy = prompt.includes("## Trust and privacy constraints");

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
            <Button
              variant="secondary"
              onClick={() => taskPackDownload.mutate()}
              loading={taskPackDownload.isPending}
            >
              <Download size={16} /> Task pack
            </Button>
            <Button
              variant="secondary"
              onClick={() => evidenceDownload.mutate()}
              loading={evidenceDownload.isPending}
            >
              <Download size={16} /> Evidence bundle
            </Button>
            <Button
              variant="secondary"
              onClick={() => promptDownload.mutate()}
              loading={promptDownload.isPending}
            >
              <Download size={16} /> Download .md
            </Button>
          </>
        }
      />

      {copyError ? (
        <StateMessage tone="danger" title="Copy did not complete">
          {copyError}
        </StateMessage>
      ) : null}
      {taskPackDownload.error ||
      evidenceDownload.error ||
      promptDownload.error ? (
        <StateMessage tone="danger" title="Protected export did not download">
          {errorMessage(
            taskPackDownload.error ??
              evidenceDownload.error ??
              promptDownload.error,
          )}
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

      {!isLoading && !isError && prompt ? (
        <>
          <Card variant="muted">
            <h2 className="text-lg font-semibold text-ink">Export readiness</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone="blue">{sectionCount} sections</Badge>
              <Badge tone="blue">{wordCount} words</Badge>
              <Badge tone={hasEvidence ? "green" : "red"}>
                {hasEvidence ? "Evidence included" : "Missing evidence"}
              </Badge>
              <Badge tone={hasRanking ? "green" : "red"}>
                {hasRanking
                  ? "Ranking rationale included"
                  : "Missing ranking rationale"}
              </Badge>
              <Badge tone={hasPrivacy ? "green" : "red"}>
                {hasPrivacy
                  ? "Privacy constraints included"
                  : "Missing privacy constraints"}
              </Badge>
            </div>
          </Card>
          <Card className="prose max-w-none break-words prose-pre:whitespace-pre-wrap prose-pre:break-words prose-code:break-words">
            <ReactMarkdown>{prompt}</ReactMarkdown>
          </Card>
        </>
      ) : null}
      {!isLoading && !isError && !prompt ? (
        <Card className="prose max-w-none break-words">
          <p>
            Process demo data first, then open a generated opportunity prompt.
          </p>
        </Card>
      ) : null}
    </div>
  );
}
