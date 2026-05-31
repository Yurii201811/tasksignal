"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card } from "@/components/ui";

export function Scans() {
  const queryClient = useQueryClient();
  const scans = useQuery({ queryKey: ["scans"], queryFn: api.scans });
  const create = useMutation({
    mutationFn: api.createScan,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scans"] })
  });
  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Scans</h1>
          <p className="mt-2 text-slate-600">Demo processing creates completed scan records. Live scheduled ingestion is documented but safe by default.</p>
        </div>
        <button
          onClick={() => create.mutate({ source: "hackernews", query: "ask", limit: 30 })}
          disabled={create.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          <Plus size={16} /> {create.isPending ? "Running scan" : "Run Ask HN scan"}
        </button>
      </div>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
              <tr>
                <th className="py-3 pr-4">Status</th>
                <th className="py-3 pr-4">Query</th>
                <th className="py-3 pr-4">Started</th>
                <th className="py-3 pr-4">Finished</th>
                <th className="py-3 pr-4">Found</th>
                <th className="py-3">Saved</th>
              </tr>
            </thead>
            <tbody>
              {(scans.data ?? []).map((scan) => (
                <tr key={scan.id} className="border-b border-slate-100">
                  <td className="py-3 pr-4"><Badge tone={scan.status === "completed" ? "green" : "amber"}>{scan.status}</Badge></td>
                  <td className="py-3 pr-4">{scan.query ?? "—"}</td>
                  <td className="py-3 pr-4">{new Date(scan.started_at).toLocaleString()}</td>
                  <td className="py-3 pr-4">{scan.finished_at ? new Date(scan.finished_at).toLocaleString() : "—"}</td>
                  <td className="py-3 pr-4">{scan.items_found}</td>
                  <td className="py-3">{scan.items_saved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
