"use client";

import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { Copy, Download } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

export function PromptView({ id }: { id: string }) {
  const { data } = useQuery({ queryKey: ["prompt", id], queryFn: () => api.prompt(id) });
  const prompt = data?.prompt ?? "Process demo data first, then open a generated opportunity prompt.";

  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Generated Codex Prompt</h1>
          <p className="mt-2 text-slate-600">Copy this into Codex to build the next evidence-backed portfolio project.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigator.clipboard.writeText(prompt)} className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white">
            <Copy size={16} /> Copy
          </button>
          <a href={api.exportUrl(id)} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink">
            <Download size={16} /> Download .md
          </a>
        </div>
      </div>
      <Card className="prose max-w-none">
        <ReactMarkdown>{prompt}</ReactMarkdown>
      </Card>
    </div>
  );
}

