"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { SearchIcon } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card } from "@/components/ui";

export function SemanticSearch() {
  const [query, setQuery] = useState("weekly spreadsheet client report");
  const search = useMutation({ mutationFn: api.semanticSearch });
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    search.mutate(query);
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-ink">Semantic search</h1>
        <p className="mt-2 text-slate-600">Search normalized evidence items using the same local embedding service as the clustering pipeline.</p>
      </div>
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="min-h-11 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-teal-100"
            placeholder="Describe a repetitive workflow"
          />
          <button className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-signal px-4 text-sm font-semibold text-white">
            <SearchIcon size={16} /> Search
          </button>
        </form>
      </Card>
      <div className="grid gap-4">
        {(search.data?.items ?? []).map((result, index) => {
          const item = result.item as { title?: string; body?: string; source?: string };
          return (
            <Card key={`${item.title}-${index}`}>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="blue">{item.source ?? "source"}</Badge>
                <Badge tone="green">Similarity {Math.round(result.similarity * 100)}</Badge>
              </div>
              <h2 className="mt-3 font-semibold text-ink">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{item.body}</p>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

