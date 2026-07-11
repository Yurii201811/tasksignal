"use client";

import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe2, Plus, ShieldCheck, ShieldX } from "lucide-react";
import { api } from "@/lib/api";
import type { Source } from "@/lib/types";
import { Badge, Button, Card, Input, StateMessage } from "@/components/ui";

function errorMessage(error: unknown) {
  if (!(error instanceof Error)) return "The request failed.";
  try {
    const detail = JSON.parse(error.message)?.detail;
    return typeof detail === "string" ? detail : error.message;
  } catch {
    return error.message;
  }
}

function readinessTone(status: string): "green" | "amber" | "red" | "slate" {
  if (status === "ready") return "green";
  if (status === "failed" || status === "disabled") return "red";
  if (status === "terms_required" || status === "retry_later") return "amber";
  return "slate";
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Never";
}

function DiscourseSourceCard({ source }: { source: Source }) {
  const queryClient = useQueryClient();
  const [origin, setOrigin] = useState("");
  const [termsConfirmed, setTermsConfirmed] = useState(false);
  const authorization = useQuery({
    queryKey: ["discourse-authorization", source.id],
    queryFn: () => api.discourseSourceAuthorization(source.id),
  });
  const runtime = useQuery({
    queryKey: ["discourse-runtime", source.id],
    queryFn: () => api.discourseSourceRuntime(source.id),
  });
  const authorize = useMutation({
    mutationFn: () => api.authorizeDiscourseSource(source.id, origin.trim()),
    onSuccess: () => {
      setTermsConfirmed(false);
      queryClient.invalidateQueries({
        queryKey: ["discourse-authorization", source.id],
      });
      queryClient.invalidateQueries({
        queryKey: ["discourse-runtime", source.id],
      });
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
  });
  const revoke = useMutation({
    mutationFn: () => api.revokeDiscourseSource(source.id),
    onSuccess: () => {
      setTermsConfirmed(false);
      queryClient.invalidateQueries({
        queryKey: ["discourse-authorization", source.id],
      });
      queryClient.invalidateQueries({
        queryKey: ["discourse-runtime", source.id],
      });
    },
  });

  useEffect(() => {
    if (authorization.data?.origin) setOrigin(authorization.data.origin);
  }, [authorization.data?.origin]);

  const status = runtime.data?.readiness ?? "never_run";
  const canAuthorize =
    origin.trim().length > 0 && termsConfirmed && !authorize.isPending;

  return (
    <Card>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <div className="flex flex-wrap gap-2">
            <Badge tone={readinessTone(status)}>
              {status.replaceAll("_", " ")}
            </Badge>
            <Badge tone={authorization.data?.authorized ? "green" : "amber"}>
              {authorization.data?.authorized
                ? "Terms confirmed"
                : "Terms required"}
            </Badge>
          </div>
          <h3 className="mt-3 font-semibold text-ink">{source.name}</h3>
          <p className="mt-1 text-sm leading-6 text-muted">
            Public only · no cookies, credentials, private categories, or raw
            author identities.
          </p>
        </div>
        <Globe2 className="h-5 w-5 shrink-0 text-signal" aria-hidden />
      </div>

      <label className="mt-4 block">
        <span className="text-sm font-semibold text-muted">
          Exact HTTPS forum origin
        </span>
        <Input
          className="mt-2"
          aria-label="Exact HTTPS forum origin"
          type="url"
          inputMode="url"
          placeholder="https://forum.example.com"
          value={origin}
          disabled={authorization.data?.authorized}
          onChange={(event) => {
            setOrigin(event.target.value);
            setTermsConfirmed(false);
          }}
        />
      </label>
      {!authorization.data?.authorized ? (
        <label className="mt-4 flex items-start gap-3 text-sm leading-6 text-muted">
          <input
            className="mt-1 h-4 w-4 rounded border-border-strong accent-[var(--ts-accent)]"
            type="checkbox"
            checked={termsConfirmed}
            onChange={(event) => setTermsConfirmed(event.target.checked)}
          />
          <span>
            I confirm this is a public forum and I accept this exact host&apos;s
            terms for bounded, read-only public-topic requests.
          </span>
        </label>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {authorization.data?.authorized ? (
          <Button
            variant="danger"
            loading={revoke.isPending}
            onClick={() => revoke.mutate()}
          >
            <ShieldX size={16} aria-hidden /> Revoke authorization
          </Button>
        ) : (
          <Button
            disabled={!canAuthorize}
            loading={authorize.isPending}
            onClick={() => authorize.mutate()}
          >
            <ShieldCheck size={16} aria-hidden /> Authorize exact host
          </Button>
        )}
      </div>

      <dl className="mt-5 grid gap-3 border-t border-border pt-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="font-semibold text-muted">Last success</dt>
          <dd className="mt-1 text-ink">
            {formatDate(runtime.data?.last_success_at ?? null)}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-muted">Retry after</dt>
          <dd className="mt-1 text-ink">
            {formatDate(runtime.data?.retry_after_at ?? null)}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-muted">Last HTTP status</dt>
          <dd className="mt-1 text-ink">
            {runtime.data?.last_http_status ?? "None"}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-muted">Sanitized failure</dt>
          <dd className="mt-1 break-words text-ink">
            {runtime.data?.last_failure_message ?? "None recorded"}
          </dd>
        </div>
      </dl>

      {authorization.error ||
      runtime.error ||
      authorize.error ||
      revoke.error ? (
        <StateMessage
          className="mt-4"
          tone="danger"
          title="Discourse source action failed"
        >
          {errorMessage(
            authorization.error ??
              runtime.error ??
              authorize.error ??
              revoke.error,
          )}
        </StateMessage>
      ) : null}
    </Card>
  );
}

export function DiscourseSourceManager({ sources }: { sources: Source[] }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => api.createDiscourseSource(name.trim()),
    onSuccess: () => {
      setName("");
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (name.trim()) create.mutate();
  }

  return (
    <section
      className="space-y-4"
      aria-labelledby="discourse-authorization-heading"
    >
      <Card variant="muted">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-end">
          <div>
            <h2
              id="discourse-authorization-heading"
              className="text-lg font-semibold text-ink"
            >
              Discourse authorization
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Each forum is locked to one exact HTTPS origin. Cross-host
              redirects, IP literals, and private network addresses are rejected
              by the connector.
            </p>
          </div>
          <form className="flex flex-col gap-2 sm:flex-row" onSubmit={submit}>
            <label className="min-w-0 flex-1">
              <span className="sr-only">Discourse source name</span>
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Forum display name"
                required
              />
            </label>
            <Button
              type="submit"
              disabled={!name.trim()}
              loading={create.isPending}
            >
              <Plus size={16} aria-hidden /> Add forum
            </Button>
          </form>
        </div>
      </Card>
      {create.error ? (
        <StateMessage tone="danger" title="Discourse source was not created">
          {errorMessage(create.error)}
        </StateMessage>
      ) : null}
      {sources.length === 0 ? (
        <StateMessage tone="warning" title="No Discourse forums yet">
          Add a display name, then authorize its exact public HTTPS origin.
        </StateMessage>
      ) : null}
      {sources.map((source) => (
        <DiscourseSourceCard key={source.id} source={source} />
      ))}
    </section>
  );
}
