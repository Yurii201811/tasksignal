"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, PieChart, Pie, Cell } from "recharts";
import { Play, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Card, ScoreBar } from "@/components/ui";

const colors = ["#0f766e", "#d97706", "#2563eb", "#7c3aed", "#dc2626"];

export function Dashboard() {
  const queryClient = useQueryClient();
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const opportunities = useQuery({ queryKey: ["opportunities"], queryFn: api.opportunities });
  const scans = useQuery({ queryKey: ["scans"], queryFn: api.scans });
  const process = useMutation({
    mutationFn: api.processDemo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
    }
  });
  const runScan = useMutation({
    mutationFn: api.createScan,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scans"] })
  });

  const metricCards = [
    ["Collected items", stats.data?.total_items ?? 0],
    ["Problem signals", stats.data?.problem_signals ?? 0],
    ["Clusters", stats.data?.clusters ?? 0],
    ["Opportunities", stats.data?.opportunities ?? 0]
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Opportunity dashboard</h1>
          <p className="mt-2 text-slate-600">Process fixture discussions into ranked, evidence-backed project ideas.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => process.mutate()}
            disabled={process.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-signal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-wait disabled:opacity-70"
          >
            {process.isPending ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
            Process demo data
          </button>
          <button
            onClick={() => runScan.mutate()}
            disabled={runScan.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-slate-50 disabled:cursor-wait disabled:opacity-70"
          >
            {runScan.isPending ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
            Run scan
          </button>
        </div>
      </div>

      {process.data && (
        <Card className="border-teal-200 bg-teal-50">
          <p className="text-sm font-semibold text-teal-900">
            Demo processed: {process.data.raw_items_loaded} raw items, {process.data.signals_detected} signals, {process.data.clusters_created} clusters, {process.data.opportunities_created} opportunities.
          </p>
        </Card>
      )}
      {scans.data?.[0] && (
        <p className="text-sm text-slate-600">
          Recent scan status: <span className="font-semibold text-ink">{scans.data[0].status}</span>
          {scans.data[0].query ? `, ${scans.data[0].query}` : ""}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metricCards.map(([label, value]) => (
          <Card key={label.toString()}>
            <p className="text-sm font-medium text-slate-500">{label}</p>
            <p className="mt-2 text-3xl font-semibold text-ink">{value}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
        <Card className="min-w-0">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-ink">Top opportunities</h2>
            <Badge tone="blue">Ranked by score</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-3 pr-4">Title</th>
                  <th className="py-3 pr-4">Score</th>
                  <th className="py-3 pr-4">Signals</th>
                  <th className="py-3 pr-4">Top source</th>
                  <th className="py-3 pr-4">Feasibility</th>
                  <th className="py-3 pr-4">Created</th>
                  <th className="py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {(opportunities.data ?? []).map((opportunity) => (
                  <tr key={opportunity.id} className="border-b border-slate-100">
                    <td className="max-w-md py-3 pr-4 font-medium text-ink">{opportunity.title}</td>
                    <td className="py-3 pr-4">{Math.round(opportunity.opportunity_score * 100)}</td>
                    <td className="py-3 pr-4">{opportunity.signal_count}</td>
                    <td className="py-3 pr-4"><Badge>{opportunity.top_source}</Badge></td>
                    <td className="py-3 pr-4"><div className="w-28"><ScoreBar value={opportunity.feasibility_score} /></div></td>
                    <td className="py-3 pr-4">{new Date(opportunity.created_at).toLocaleDateString()}</td>
                    <td className="py-3"><Link className="font-semibold text-signal" href={`/opportunities/${opportunity.id}`}>Open</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="grid min-w-0 gap-4 md:grid-cols-2 2xl:grid-cols-1">
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-ink">Source breakdown</h2>
            <div className="h-56">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={stats.data?.source_breakdown ?? []} dataKey="count" nameKey="source" outerRadius={82} label>
                    {(stats.data?.source_breakdown ?? []).map((entry, index) => <Cell key={entry.source} fill={colors[index % colors.length]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-ink">Pain score distribution</h2>
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={stats.data?.pain_distribution ?? []}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#0f766e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
