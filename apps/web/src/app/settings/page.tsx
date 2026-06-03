"use client";

import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  KeyRound,
  Play,
  RefreshCw,
  Save,
  ShieldCheck,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import {
  Badge,
  Button,
  Card,
  Input,
  PageHeader,
  Select,
  StateMessage,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { Integration } from "@/lib/types";

const sourceOptions = [
  { value: "hackernews", label: "Hacker News" },
  { value: "fixture", label: "Fixture files" },
  { value: "github", label: "GitHub Issues" },
  { value: "reddit", label: "Reddit" },
  { value: "stackexchange", label: "Stack Exchange" },
];

const cadenceOptions = [
  { value: "manual", label: "Manual" },
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "custom", label: "Custom" },
];

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
  const queryClient = useQueryClient();
  const [operatorToken, setOperatorToken] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [workspaceGoal, setWorkspaceGoal] = useState("");
  const [defaultSourceType, setDefaultSourceType] = useState("hackernews");
  const [defaultQuery, setDefaultQuery] = useState("ask");
  const [defaultLimit, setDefaultLimit] = useState(30);
  const [defaultCadence, setDefaultCadence] = useState("manual");
  const [defaultIntervalHours, setDefaultIntervalHours] = useState(24);
  const integrations = useQuery({
    queryKey: ["integrations"],
    queryFn: api.integrations,
  });
  const localWorkspace = useQuery({
    queryKey: ["local-workspace"],
    queryFn: api.localWorkspace,
  });
  const readiness = useQuery({
    queryKey: ["readiness"],
    queryFn: api.readiness,
  });
  const saveWorkspace = useMutation({
    mutationFn: api.updateLocalWorkspace,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["local-workspace"] });
      queryClient.invalidateQueries({ queryKey: ["readiness"] });
    },
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

  useEffect(() => {
    if (!localWorkspace.data) return;
    setOwnerName(localWorkspace.data.owner_name);
    setWorkspaceGoal(localWorkspace.data.workspace_goal);
    setDefaultSourceType(localWorkspace.data.default_source_type);
    setDefaultQuery(localWorkspace.data.default_query);
    setDefaultLimit(localWorkspace.data.default_limit);
    setDefaultCadence(localWorkspace.data.default_cadence);
    setDefaultIntervalHours(
      localWorkspace.data.default_schedule_interval_hours ?? 24,
    );
  }, [localWorkspace.data]);

  function updateOperatorToken(value: string) {
    setOperatorToken(value);
    window.localStorage.setItem("tasksignal.operatorToken", value);
  }

  function submitWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    saveWorkspace.mutate({
      owner_name: ownerName.trim(),
      workspace_goal: workspaceGoal.trim(),
      default_source_type: defaultSourceType,
      default_query: defaultQuery.trim(),
      default_limit: defaultLimit,
      default_cadence: defaultCadence,
      default_schedule_interval_hours:
        defaultCadence === "custom" ? Math.max(1, defaultIntervalHours) : null,
    });
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          title="Integrations"
          description="Connect public sources, optional API credentials, and agent handoff paths without exposing secret values in the browser."
        />

        <Card>
          <form className="space-y-4" onSubmit={submitWorkspace}>
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
              <div>
                <div className="flex flex-wrap gap-2">
                  <Badge tone={localWorkspace.data?.configured ? "green" : "amber"}>
                    {localWorkspace.data?.configured
                      ? "Local user set"
                      : "Local user not set"}
                  </Badge>
                  <Badge>Single-machine workspace</Badge>
                </div>
                <h2 className="mt-3 text-lg font-semibold text-ink">
                  Local workspace
                </h2>
              </div>
              <Button
                type="submit"
                variant="secondary"
                loading={saveWorkspace.isPending}
                disabled={saveWorkspace.isPending}
              >
                {saveWorkspace.isPending ? (
                  <RefreshCw className="animate-spin" size={16} />
                ) : (
                  <Save size={16} />
                )}
                Save workspace
              </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">
                  Local owner
                </span>
                <Input
                  value={ownerName}
                  onChange={(event) => setOwnerName(event.target.value)}
                  className="mt-2"
                  placeholder="Your name or team"
                />
              </label>
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">
                  Research focus
                </span>
                <Input
                  value={workspaceGoal}
                  onChange={(event) => setWorkspaceGoal(event.target.value)}
                  className="mt-2"
                  placeholder="Developer-tool ideas, support automation..."
                />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_110px]">
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">
                  Default source
                </span>
                <Select
                  value={defaultSourceType}
                  onChange={(event) => setDefaultSourceType(event.target.value)}
                  className="mt-2"
                >
                  {sourceOptions.map((source) => (
                    <option key={source.value} value={source.value}>
                      {source.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">
                  Default query
                </span>
                <Input
                  value={defaultQuery}
                  onChange={(event) => setDefaultQuery(event.target.value)}
                  className="mt-2"
                />
              </label>
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">Limit</span>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={defaultLimit}
                  onChange={(event) =>
                    setDefaultLimit(
                      Math.max(
                        1,
                        Math.min(100, Number(event.target.value) || 1),
                      ),
                    )
                  }
                  className="mt-2"
                />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_150px]">
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">
                  Default cadence
                </span>
                <Select
                  value={defaultCadence}
                  onChange={(event) => setDefaultCadence(event.target.value)}
                  className="mt-2"
                >
                  {cadenceOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="block min-w-0">
                <span className="text-sm font-semibold text-muted">Hours</span>
                <Input
                  type="number"
                  min={1}
                  max={744}
                  value={defaultIntervalHours}
                  onChange={(event) =>
                    setDefaultIntervalHours(
                      Math.max(
                        1,
                        Math.min(744, Number(event.target.value) || 1),
                      ),
                    )
                  }
                  className="mt-2"
                  disabled={defaultCadence !== "custom"}
                />
              </label>
            </div>
          </form>
        </Card>

        {saveWorkspace.error ? (
          <StateMessage tone="danger" title="Workspace was not saved">
            {errorMessage(saveWorkspace.error)}
          </StateMessage>
        ) : null}
        {saveWorkspace.data ? (
          <StateMessage tone="success" title="Workspace saved">
            Project defaults now use this local-machine profile.
          </StateMessage>
        ) : null}

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

        {readiness.data ? (
          <Card>
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
              <div>
                <div className="flex flex-wrap gap-2">
                  <Badge
                    tone={readiness.data.status === "ready" ? "green" : "red"}
                  >
                    {readiness.data.status}
                  </Badge>
                  <Badge>
                    Projects: {String(readiness.data.checks.projects ?? 0)}
                  </Badge>
                  <Badge>
                    Opportunities:{" "}
                    {String(readiness.data.checks.opportunities ?? 0)}
                  </Badge>
                  <Badge>
                    Due: {String(readiness.data.checks.due_projects ?? 0)}
                  </Badge>
                </div>
                <h2 className="mt-3 text-lg font-semibold text-ink">
                  Workspace readiness
                </h2>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => readiness.refetch()}
                loading={readiness.isFetching}
                disabled={readiness.isFetching}
              >
                <RefreshCw
                  size={15}
                  className={readiness.isFetching ? "animate-spin" : ""}
                />
                Refresh
              </Button>
            </div>
            {readiness.data.blockers.length > 0 ? (
              <ul className="mt-4 grid gap-2 text-sm text-danger">
                {readiness.data.blockers.map((blocker) => (
                  <li key={blocker}>{blocker}</li>
                ))}
              </ul>
            ) : null}
            {readiness.data.warnings.length > 0 ? (
              <ul className="mt-4 grid gap-2 text-sm text-muted">
                {readiness.data.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </Card>
        ) : null}

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
