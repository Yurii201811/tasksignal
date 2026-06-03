"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  KeyRound,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import {
  Badge,
  Button,
  Card,
  Input,
  PageHeader,
  StateMessage,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { Integration } from "@/lib/types";

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    try {
      const parsed = JSON.parse(error.message);
      if (parsed?.detail) {
        return typeof parsed.detail === "string"
          ? parsed.detail
          : JSON.stringify(parsed.detail);
      }
    } catch {
      return error.message;
    }
  }
  return "The request failed.";
}

function statusTone(
  status: string,
): "green" | "amber" | "blue" | "red" | "slate" {
  if (status === "ready" || status === "available") return "green";
  if (status === "ready_limited") return "amber";
  if (status === "missing_credentials") return "red";
  if (status === "ok") return "green";
  return "blue";
}

function credentialLabel(integration: Integration) {
  if (integration.credential_state === "not_required")
    return "No secret required";
  if (integration.credential_state === "configured")
    return "Credential configured";
  if (integration.credential_state === "optional_missing")
    return "Optional credential missing";
  return "Missing credential";
}

export default function SettingsPage() {
  const [operatorToken, setOperatorToken] = useState("");
  const integrations = useQuery({
    queryKey: ["integrations"],
    queryFn: api.integrations,
  });
  const test = useMutation({
    mutationFn: (id: string) =>
      api.testIntegration(id, operatorToken.trim() || undefined),
  });

  useEffect(() => {
    setOperatorToken(
      window.localStorage.getItem("tasksignal.operatorToken") ?? "",
    );
  }, []);

  function updateOperatorToken(value: string) {
    setOperatorToken(value);
    window.localStorage.setItem("tasksignal.operatorToken", value);
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          title="Integrations"
          description="Connect public sources, optional API credentials, and agent handoff paths without exposing secret values in the browser."
        />

        <Card variant="muted">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
            <div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="green">Local-first</Badge>
                <Badge tone="blue">Codex task packs</Badge>
                <Badge tone="amber">Credentialed scans gated</Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted">
                Public scans can run directly. Credentialed GitHub, Reddit, and
                Stack Exchange scans require an API-side `OPERATOR_SCAN_TOKEN`
                plus the matching local token here, so a hosted deployment
                cannot accidentally spend server-side credentials.
              </p>
            </div>
            <label className="block">
              <span className="text-sm font-semibold text-muted">
                Local operator token
              </span>
              <Input
                value={operatorToken}
                onChange={(event) => updateOperatorToken(event.target.value)}
                type="password"
                className="mt-2"
                placeholder="Required for credentialed tests"
              />
            </label>
          </div>
        </Card>

        {integrations.error ? (
          <StateMessage tone="danger" title="Could not load integrations">
            {errorMessage(integrations.error)}
          </StateMessage>
        ) : null}
        {integrations.isLoading ? (
          <StateMessage tone="info" title="Loading integration status">
            Checking source, runtime, and Codex handoff readiness.
          </StateMessage>
        ) : null}
        {test.error ? (
          <StateMessage tone="danger" title="Integration test did not complete">
            {errorMessage(test.error)}
          </StateMessage>
        ) : null}
        {test.data ? (
          <StateMessage
            tone={test.data.status === "ok" ? "success" : "warning"}
            title={`Test result: ${test.data.id}`}
          >
            {test.data.detail}
          </StateMessage>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          {(integrations.data ?? []).map((integration) => (
            <Card key={integration.id}>
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={statusTone(integration.status)}>
                      {integration.status.replace("_", " ")}
                    </Badge>
                    <Badge>{integration.kind.replace("_", " ")}</Badge>
                    {integration.public_scan_enabled ? (
                      <Badge tone="green">Public scan</Badge>
                    ) : null}
                    {integration.operator_token_required ? (
                      <Badge tone="amber">Operator gated</Badge>
                    ) : null}
                  </div>
                  <h2 className="mt-3 break-words text-lg font-semibold text-ink">
                    {integration.name}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {integration.next_step}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => test.mutate(integration.id)}
                  loading={test.isPending && test.variables === integration.id}
                  disabled={test.isPending}
                >
                  {test.isPending && test.variables === integration.id ? (
                    <RefreshCw className="animate-spin" size={15} />
                  ) : (
                    <Play size={15} />
                  )}
                  Test
                </Button>
              </div>

              <div className="mt-4 grid gap-3 border-t border-border pt-4 text-sm leading-6">
                <div className="flex gap-2">
                  <KeyRound className="mt-1 h-4 w-4 shrink-0 text-signal" />
                  <span className="text-muted">
                    {credentialLabel(integration)}
                  </span>
                </div>
                <div className="flex gap-2">
                  <ShieldCheck className="mt-1 h-4 w-4 shrink-0 text-signal" />
                  <span className="text-muted">{integration.privacy_note}</span>
                </div>
                <div className="flex gap-2">
                  <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-signal" />
                  <span className="text-muted">
                    {integration.rate_limit_note}
                  </span>
                </div>
              </div>

              {integration.required_env.length > 0 ||
              integration.optional_env.length > 0 ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {integration.required_env.map((name) => (
                    <Badge key={name} tone="red">
                      {name}
                    </Badge>
                  ))}
                  {integration.optional_env.map((name) => (
                    <Badge key={name} tone="blue">
                      {name}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {integration.last_scan_status ? (
                <p className="mt-4 border-t border-border pt-4 text-sm text-muted">
                  Last scan: {integration.last_scan_status}
                  {integration.last_scan_at
                    ? ` at ${new Date(integration.last_scan_at).toLocaleString()}`
                    : ""}
                </p>
              ) : null}
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
