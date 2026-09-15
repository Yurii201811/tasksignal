"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { refreshReviewQueries } from "@/lib/research-cache";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { EVIDENCE_REVIEW_OPTIONS, evidenceReviewLabel } from "@/lib/review";
import type { EvidenceItem, EvidenceReviewLabel } from "@/lib/types";
import { Badge, Button, Select, StateMessage, Textarea } from "@/components/ui";

export function EvidenceReviewControl({
  item,
  onDirtyChange,
}: {
  opportunityId: string;
  item: EvidenceItem;
  onDirtyChange?: (id: string, dirty: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState<EvidenceReviewLabel | "">(
    item.review_label ?? "",
  );
  const [note, setNote] = useState("");
  const edited = useRef(false);
  const draftItem = useRef(item.id);
  useEffect(() => {
    if (draftItem.current === item.id && edited.current) return;
    draftItem.current = item.id;
    edited.current = false;
    setLabel(item.review_label ?? "");
    setNote("");
  }, [item.id, item.review_label]);
  const mutation = useMutation({
    mutationFn: (reviewLabel: EvidenceReviewLabel) =>
      api.createEvidenceReview({
        item_id: item.id,
        label: reviewLabel,
        user_note: note.trim() || null,
      }),
    onSuccess: async () => {
      edited.current = false;
      await Promise.all([
        refreshReviewQueries(queryClient),
        queryClient.invalidateQueries({ queryKey: ["item-labels", item.id] }),
      ]);
      setNote("");
    },
  });

  const dirty =
    label !== (item.review_label ?? "") || Boolean(note) || mutation.isPending;
  useEffect(() => {
    onDirtyChange?.(item.id, dirty);
  }, [dirty, item.id, onDirtyChange]);

  function clearMutationFeedback() {
    if (mutation.isSuccess || mutation.isError) mutation.reset();
  }

  return (
    <div className="mt-4 border-t border-border pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-ink">Evidence review</span>
        {item.review_label ? (
          <Badge>{evidenceReviewLabel(item.review_label)}</Badge>
        ) : null}
        {!item.review_label && item.review_history_count > 0 ? (
          <Badge>No current recognized label</Badge>
        ) : null}
        <span className="text-xs text-muted">
          {item.review_history_count} stored review(s)
        </span>
      </div>
      {item.review_note ? (
        <p className="mt-2 text-sm text-muted">
          Current note: {item.review_note}
        </p>
      ) : null}
      {item.reviewed_at ? (
        <time
          className="mt-1 block text-xs text-muted"
          dateTime={item.reviewed_at}
        >
          {new Date(item.reviewed_at).toLocaleString()}
        </time>
      ) : null}
      <div className="mt-3 grid gap-3 md:grid-cols-[220px_minmax(0,1fr)_auto] md:items-end">
        <label>
          <span className="text-xs font-semibold text-muted">
            Evidence label
          </span>
          <Select
            className="mt-1"
            disabled={mutation.isPending}
            value={label}
            onChange={(event) => {
              edited.current = true;
              clearMutationFeedback();
              setLabel(event.target.value as EvidenceReviewLabel | "");
            }}
            required
          >
            <option value="" disabled>
              Select a label
            </option>
            {EVIDENCE_REVIEW_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </label>
        <label>
          <span className="text-xs font-semibold text-muted">
            New evidence review note
          </span>
          <Textarea
            className="mt-1 min-h-20"
            disabled={mutation.isPending}
            maxLength={500}
            value={note}
            onChange={(event) => {
              edited.current = true;
              clearMutationFeedback();
              setNote(event.target.value);
            }}
          />
        </label>
        <Button
          onClick={() => {
            if (label) mutation.mutate(label);
          }}
          loading={mutation.isPending}
          disabled={!label}
          title={!label ? "Choose an evidence label first." : undefined}
        >
          Add evidence review
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted">
        Saving adds a review; it does not edit prior history. Notes stay out of
        exports.
      </p>
      {mutation.error ? (
        <StateMessage
          className="mt-3"
          tone="danger"
          title="Evidence review was not saved"
        >
          {apiErrorMessage(mutation.error)}
        </StateMessage>
      ) : null}
      {mutation.isSuccess ? (
        <StateMessage
          className="mt-3"
          tone="success"
          title="Evidence review added"
        />
      ) : null}
    </div>
  );
}
