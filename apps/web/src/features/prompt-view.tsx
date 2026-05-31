"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, Copy, Download } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

export function PromptView({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);
  const { data, error, isError, isLoading } = useQuery({
    queryKey: ["prompt", id],
    queryFn: () => api.prompt(id),
  });
  const prompt = data?.prompt ?? "";

  async function copyPrompt() {
    if (!prompt) return;
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <Link
            href={`/opportunities/${id}`}
            className="inline-flex items-center gap-1 text-sm font-semibold text-signal"
          >
            <ArrowLeft size={15} /> Back to evidence
          </Link>
          <h1 className="mt-3 text-3xl font-semibold text-ink">
            Generated Codex Prompt
          </h1>
          <p className="mt-2 text-slate-600">
            Copy this into Codex with the evidence excerpts, ranking rationale,
            and privacy constraints intact.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={copyPrompt}
            disabled={!prompt}
            className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Copy size={16} /> {copied ? "Copied" : "Copy"}
          </button>
          <a
            href={api.exportUrl(id)}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink"
          >
            <Download size={16} /> Download .md
          </a>
        </div>
      </div>
      {isLoading && <Card>Loading generated prompt...</Card>}
      {isError && (
        <Card>
          Could not load generated prompt:{" "}
          {error instanceof Error ? error.message : "The request failed."}
        </Card>
      )}
      {!isLoading && !isError && (
        <Card className="prose max-w-none">
          <ReactMarkdown>
            {prompt ||
              "Process demo data first, then open a generated opportunity prompt."}
          </ReactMarkdown>
        </Card>
      )}
    </div>
  );
}
