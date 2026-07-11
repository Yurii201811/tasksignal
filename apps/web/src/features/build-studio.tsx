"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  Download,
  FileText,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import type { BuildPacket, OpportunityThread } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  Select,
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

export function BuildStudio({ thread }: { thread: OpportunityThread }) {
  const queryClient = useQueryClient();
  const [selectedPacketId, setSelectedPacketId] = useState<string | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState("README.md");
  const packets = useQuery({
    queryKey: ["build-packets", thread.id],
    queryFn: () => api.buildPackets(thread.id),
  });
  const storedPacket = useQuery({
    queryKey: ["build-packet", selectedPacketId],
    queryFn: () => api.buildPacket(selectedPacketId as string),
    enabled: selectedPacketId !== null,
  });
  const create = useMutation({
    mutationFn: (useConfiguredAi: boolean) =>
      api.createBuildPacket(thread.id, {
        expected_version: thread.version,
        use_configured_ai: useConfiguredAi,
      }),
    onSuccess: (packet) => {
      setSelectedPacketId(null);
      setSelectedArtifact("README.md");
      queryClient.invalidateQueries({ queryKey: ["build-packets", thread.id] });
      return packet;
    },
  });
  const verify = useMutation({ mutationFn: api.verifyBuildPacket });
  const downloadPacket = useMutation({ mutationFn: api.downloadBuildPacket });
  const currentPacket: BuildPacket | undefined = selectedPacketId
    ? storedPacket.data
    : create.data;
  const selectedContent = currentPacket?.artifacts.find(
    (artifact) => artifact.path === selectedArtifact,
  );
  const current = thread.current_snapshot;
  const hasSensitiveRisk = Boolean(
    current?.evidence_items.some(
      (item) => item.review_label === "sensitive_risk",
    ),
  );
  const eligible = Boolean(
    thread.review_state === "build_candidate" &&
    current &&
    current.evidence_readiness.level !== "weak" &&
    !hasSensitiveRisk,
  );

  useEffect(() => {
    if (
      !currentPacket?.artifacts.some((item) => item.path === selectedArtifact)
    ) {
      setSelectedArtifact(currentPacket?.artifacts[0]?.path ?? "README.md");
    }
  }, [currentPacket, selectedArtifact]);

  return (
    <section className="space-y-4" aria-labelledby="build-studio-heading">
      <Card variant="muted">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <div className="flex flex-wrap gap-2">
              <Badge tone={eligible ? "green" : "amber"}>
                {eligible ? "Eligible" : "Eligibility blocked"}
              </Badge>
              <Badge>Immutable originals retained</Badge>
            </div>
            <h2
              id="build-studio-heading"
              className="mt-3 text-lg font-semibold text-ink"
            >
              Build Studio
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
              Generate the complete deterministic evidence-to-build suite,
              inspect its stored artifacts, verify hashes, and download the
              immutable ZIP.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              loading={create.isPending && create.variables === false}
              disabled={!eligible || create.isPending}
              onClick={() => create.mutate(false)}
            >
              <FileText size={16} aria-hidden /> Generate deterministic packet
            </Button>
            <Button
              loading={create.isPending && create.variables === true}
              disabled={!eligible || create.isPending}
              onClick={() => create.mutate(true)}
            >
              <Bot size={16} aria-hidden /> Generate with configured AI
            </Button>
          </div>
        </div>
        <p className="mt-3 text-xs leading-5 text-muted">
          Configured AI is optional and may incur provider cost. Deterministic
          originals remain authoritative in every packet.
        </p>
      </Card>

      {!eligible ? (
        <StateMessage tone="warning" title="Packet generation is guarded">
          Mark the thread as a build candidate, reach medium or strong evidence
          readiness, and clear any current human-confirmed sensitive risk.
        </StateMessage>
      ) : null}
      {create.error ? (
        <StateMessage tone="danger" title="Packet was not created">
          {errorMessage(create.error)}
        </StateMessage>
      ) : null}

      {(packets.data ?? []).length > 0 ? (
        <Card>
          <h3 className="font-semibold text-ink">Stored packet snapshots</h3>
          <TableShell
            className="mt-3"
            label="Stored build packets"
            tableClassName="min-w-[720px]"
          >
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="py-3 pr-4">Generated</th>
                <th className="py-3 pr-4">Mode</th>
                <th className="py-3 pr-4">Artifacts</th>
                <th className="py-3 text-right">View</th>
              </tr>
            </thead>
            <tbody>
              {(packets.data ?? []).map((packet) => (
                <tr
                  key={packet.id}
                  className="border-b border-border last:border-0"
                >
                  <td className="py-3 pr-4 text-muted">
                    {new Date(packet.generated_at).toLocaleString()}
                  </td>
                  <td className="py-3 pr-4">
                    <Badge>{packet.generation_mode}</Badge>
                  </td>
                  <td className="py-3 pr-4 tabular-nums text-muted">
                    {packet.artifact_count}
                  </td>
                  <td className="py-3 text-right">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setSelectedPacketId(packet.id)}
                    >
                      View packet
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Card>
      ) : null}

      {storedPacket.isLoading ? (
        <StateMessage tone="info" title="Loading packet artifacts">
          Reading the immutable stored snapshot.
        </StateMessage>
      ) : null}

      {currentPacket ? (
        <Card>
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
            <div>
              <div className="flex flex-wrap gap-2">
                <Badge tone="blue">{currentPacket.generation_mode}</Badge>
                <Badge>{currentPacket.artifacts.length} files</Badge>
                <Badge>{currentPacket.tasksignal_version}</Badge>
              </div>
              <h3 className="mt-3 font-semibold text-ink">
                Packet {currentPacket.id}
              </h3>
              <p className="mt-1 break-all font-mono text-xs text-muted">
                Manifest SHA-256: {currentPacket.manifest_sha256}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                loading={verify.isPending}
                onClick={() => verify.mutate(currentPacket.id)}
              >
                <ShieldCheck size={16} aria-hidden /> Verify packet
              </Button>
              <Button
                loading={downloadPacket.isPending}
                onClick={() => downloadPacket.mutate(currentPacket.id)}
              >
                <Download size={16} aria-hidden /> Download ZIP
              </Button>
            </div>
          </div>

          {verify.data ? (
            <StateMessage
              className="mt-4"
              tone={verify.data.valid ? "success" : "danger"}
              title={
                verify.data.valid
                  ? "Integrity verified"
                  : "Integrity check failed"
              }
            >
              {verify.data.valid
                ? "Every stored artifact matches its manifest byte count and SHA-256 hash."
                : verify.data.errors.join(" ")}
            </StateMessage>
          ) : null}
          {verify.error ? (
            <StateMessage
              className="mt-4"
              tone="danger"
              title="Verification failed"
            >
              {errorMessage(verify.error)}
            </StateMessage>
          ) : null}
          {downloadPacket.error ? (
            <StateMessage
              className="mt-4"
              tone="danger"
              title="Packet download failed"
            >
              {errorMessage(downloadPacket.error)}
            </StateMessage>
          ) : null}

          <div className="mt-5 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
            <div>
              <label
                className="text-sm font-semibold text-muted"
                htmlFor="packet-artifact"
              >
                Artifact
              </label>
              <Select
                id="packet-artifact"
                className="mt-2"
                value={selectedArtifact}
                onChange={(event) => setSelectedArtifact(event.target.value)}
              >
                {currentPacket.artifacts.map((artifact) => (
                  <option key={artifact.path} value={artifact.path}>
                    {artifact.path}
                  </option>
                ))}
              </Select>
              <div className="mt-3 grid gap-2">
                {currentPacket.artifacts.map((artifact) => (
                  <button
                    key={artifact.path}
                    type="button"
                    className="min-h-11 break-all rounded-product border border-border px-3 py-2 text-left text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ts-focus-ring)]"
                    onClick={() => setSelectedArtifact(artifact.path)}
                  >
                    {artifact.path}
                  </button>
                ))}
              </div>
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-ink">
                  {selectedContent?.path}
                </p>
                {selectedContent ? (
                  <span className="inline-flex items-center gap-1 text-xs text-success">
                    <CheckCircle2 size={14} aria-hidden />{" "}
                    {selectedContent.byte_count} bytes
                  </span>
                ) : null}
              </div>
              <pre className="mt-2 max-h-[520px] overflow-auto rounded-product bg-[var(--color-ink)] p-4 text-xs leading-6 text-[var(--color-paper-2)]">
                <code>{selectedContent?.content ?? "Select an artifact."}</code>
              </pre>
            </div>
          </div>
        </Card>
      ) : null}

      {create.isPending ? (
        <StateMessage tone="info" title="Generating immutable packet">
          <span className="inline-flex items-center gap-2">
            <RefreshCw
              size={14}
              className="motion-safe:animate-spin"
              aria-hidden
            />
            Deterministic documents are being rendered and verified before
            storage.
          </span>
        </StateMessage>
      ) : null}
    </section>
  );
}
