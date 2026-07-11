"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, Eye, RefreshCw, ShieldX } from "lucide-react";
import { api } from "@/lib/api";
import type { AgentSession } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  PageHeader,
  StateMessage,
  TableShell,
} from "@/components/ui";

function errorMessage(error: unknown) {
  if (!(error instanceof Error)) return "The request failed.";
  try {
    const detail = JSON.parse(error.message)?.detail;
    return typeof detail === "string" ? detail : error.message;
  } catch {
    return error.message;
  }
}

function sessionTone(
  status: AgentSession["effective_status"],
): "green" | "amber" | "red" | "slate" {
  if (status === "approved") return "green";
  if (status === "pending") return "amber";
  if (status === "revoked") return "red";
  return "slate";
}

export function AgentSessions() {
  const queryClient = useQueryClient();
  const [configuredAiBySession, setConfiguredAiBySession] = useState<
    Record<string, boolean>
  >({});
  const [auditSessionId, setAuditSessionId] = useState<string | null>(null);
  const sessions = useQuery({
    queryKey: ["agent-sessions"],
    queryFn: api.agentSessions,
  });
  const audit = useQuery({
    queryKey: ["agent-session-actions", auditSessionId],
    queryFn: () => api.agentSessionActions(auditSessionId as string),
    enabled: auditSessionId !== null,
  });
  const approve = useMutation({
    mutationFn: (session: AgentSession) =>
      api.approveAgentSession(
        session.id,
        session.version,
        configuredAiBySession[session.id] ?? false,
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["agent-sessions"] }),
  });
  const revoke = useMutation({
    mutationFn: (session: AgentSession) =>
      api.revokeAgentSession(session.id, session.version),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["agent-sessions"] }),
  });
  const error = sessions.error ?? approve.error ?? revoke.error;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent sessions"
        description="Approve process-bound MCP write access, monitor its short heartbeat lease, revoke it immediately, and inspect a redacted append-only action audit."
      />

      <Card variant="muted">
        <div className="flex items-start gap-3">
          <Bot className="mt-1 h-5 w-5 shrink-0 text-signal" aria-hidden />
          <div>
            <h2 className="font-semibold text-ink">
              Writes require a live, approved process
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Approval ends when that MCP process exits or misses two
              heartbeats. Shell, filesystem, credentials, deletion, retention,
              host authorization, and direct GitHub writes are never exposed.
            </p>
          </div>
        </div>
      </Card>

      {error ? (
        <StateMessage tone="danger" title="Agent session action failed">
          {errorMessage(error)}
        </StateMessage>
      ) : null}
      {sessions.isLoading ? (
        <StateMessage tone="info" title="Loading agent sessions">
          Expiring missed heartbeat leases before showing current state.
        </StateMessage>
      ) : null}
      {!sessions.isLoading && (sessions.data ?? []).length === 0 ? (
        <StateMessage tone="warning" title="No agent sessions">
          Start `tasksignal mcp` to register a process and request guarded write
          access.
        </StateMessage>
      ) : null}

      <div className="grid gap-4">
        {(sessions.data ?? []).map((session) => {
          const pending = session.effective_status === "pending";
          const approved = session.effective_status === "approved";
          return (
            <Card key={session.id}>
              <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={sessionTone(session.effective_status)}>
                      {session.effective_status}
                    </Badge>
                    <Badge>{session.transport}</Badge>
                    <Badge>version {session.version}</Badge>
                  </div>
                  <h2 className="mt-3 break-words text-lg font-semibold text-ink">
                    {session.client_name}
                  </h2>
                  <p className="mt-1 text-sm text-muted">
                    {session.client_version
                      ? `Client ${session.client_version} · `
                      : ""}
                    Process {session.process_instance_id}
                  </p>
                  <p className="mt-2 text-sm text-muted">
                    Last heartbeat{" "}
                    {new Date(session.last_heartbeat_at).toLocaleString()} ·
                    lease expires{" "}
                    {new Date(session.expires_at).toLocaleString()}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {session.requested_capabilities.map((capability) => (
                      <Badge key={capability}>
                        {capability.replaceAll("_", " ")}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="flex max-w-md flex-col items-start gap-3 lg:items-end">
                  {pending ? (
                    <label className="flex items-start gap-3 text-sm leading-6 text-muted">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 rounded border-border-strong accent-[var(--ts-accent)]"
                        checked={configuredAiBySession[session.id] ?? false}
                        onChange={(event) =>
                          setConfiguredAiBySession((current) => ({
                            ...current,
                            [session.id]: event.target.checked,
                          }))
                        }
                      />
                      <span>
                        Also approve configured AI packet enhancement (may incur
                        provider cost)
                      </span>
                    </label>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {pending ? (
                      <Button
                        loading={
                          approve.isPending &&
                          approve.variables?.id === session.id
                        }
                        disabled={approve.isPending}
                        onClick={() => approve.mutate(session)}
                      >
                        <Check size={16} aria-hidden /> Approve session
                      </Button>
                    ) : null}
                    {approved ? (
                      <Button
                        variant="danger"
                        loading={
                          revoke.isPending &&
                          revoke.variables?.id === session.id
                        }
                        disabled={revoke.isPending}
                        onClick={() => revoke.mutate(session)}
                      >
                        <ShieldX size={16} aria-hidden /> Revoke session
                      </Button>
                    ) : null}
                    <Button
                      variant="secondary"
                      onClick={() => setAuditSessionId(session.id)}
                    >
                      <Eye size={16} aria-hidden /> View redacted audit
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {auditSessionId ? (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-ink">
                Redacted action audit
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                Request and result summaries are redacted by the API before they
                reach this UI. Raw session secrets and credentials are never
                returned.
              </p>
            </div>
            <Badge>{audit.data?.length ?? 0} events</Badge>
          </div>
          {audit.isLoading ? (
            <p className="mt-4 inline-flex items-center gap-2 text-sm text-muted">
              <RefreshCw
                size={14}
                className="motion-safe:animate-spin"
                aria-hidden
              />{" "}
              Loading audit
            </p>
          ) : null}
          {audit.error ? (
            <StateMessage
              className="mt-4"
              tone="danger"
              title="Could not load action audit"
            >
              {errorMessage(audit.error)}
            </StateMessage>
          ) : null}
          {(audit.data ?? []).length > 0 ? (
            <TableShell
              className="mt-4"
              label="Redacted agent action audit"
              caption="Append-only redacted MCP action events"
              tableClassName="min-w-[980px]"
            >
              <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="py-3 pr-4">Time / status</th>
                  <th className="py-3 pr-4">Tool</th>
                  <th className="py-3 pr-4">Target</th>
                  <th className="py-3 pr-4">Request summary</th>
                  <th className="py-3">Result summary</th>
                </tr>
              </thead>
              <tbody>
                {(audit.data ?? []).map((action) => (
                  <tr
                    key={action.id}
                    className="border-b border-border last:border-0"
                  >
                    <td className="py-4 pr-4 align-top">
                      <Badge
                        tone={
                          action.event_status === "succeeded"
                            ? "green"
                            : action.event_status === "failed"
                              ? "red"
                              : "slate"
                        }
                      >
                        {action.event_status}
                      </Badge>
                      <p className="mt-2 text-xs text-muted">
                        {new Date(action.created_at).toLocaleString()}
                      </p>
                    </td>
                    <td className="py-4 pr-4 align-top">
                      <code className="text-xs font-semibold text-ink">
                        {action.tool_name}
                      </code>
                      <p className="mt-1 text-xs text-muted">
                        {action.capability.replaceAll("_", " ")}
                      </p>
                    </td>
                    <td className="py-4 pr-4 align-top text-xs text-muted">
                      {action.target_type ?? "—"} {action.target_id ?? ""}
                    </td>
                    <td className="py-4 pr-4 align-top">
                      <pre className="max-w-sm whitespace-pre-wrap break-all font-mono text-xs leading-5 text-muted">
                        {JSON.stringify(action.request_summary, null, 2)}
                      </pre>
                    </td>
                    <td className="py-4 align-top">
                      <pre className="max-w-sm whitespace-pre-wrap break-all font-mono text-xs leading-5 text-muted">
                        {JSON.stringify(action.result_summary, null, 2)}
                      </pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableShell>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
