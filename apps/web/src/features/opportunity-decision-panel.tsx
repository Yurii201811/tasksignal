"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { REVIEW_STATE_OPTIONS, reviewStateOption } from "@/lib/review";
import type { ReviewState } from "@/lib/types";
import {
  Badge,
  Button,
  Card,
  Select,
  StateMessage,
  Textarea,
} from "@/components/ui";

export function OpportunityDecisionPanel({
  opportunityId,
  reviewState,
  reviewNote,
  decisionUpdatedAt,
}: {
  opportunityId: string;
  reviewState: ReviewState;
  reviewNote: string | null;
  decisionUpdatedAt: string | null;
}) {
  const queryClient = useQueryClient();
  const [draftState, setDraftState] = useState<ReviewState>(reviewState);
  const [draftNote, setDraftNote] = useState(reviewNote ?? "");
  const mutation = useMutation({
    mutationFn: () =>
      api.updateOpportunityReview(opportunityId, {
        review_state: draftState,
        review_note: draftNote.trim() || null,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["opportunity", opportunityId],
        }),
        queryClient.invalidateQueries({ queryKey: ["opportunities"] }),
      ]);
    },
  });
  const confirmed = reviewStateOption(reviewState);

  useEffect(() => {
    setDraftState(reviewState);
    setDraftNote(reviewNote ?? "");
  }, [decisionUpdatedAt, opportunityId, reviewNote, reviewState]);

  function clearMutationFeedback() {
    if (mutation.isSuccess || mutation.isError) mutation.reset();
  }

  return (
    <Card className="space-y-4" aria-label="Opportunity decision">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Decision</h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            Only the local operator can promote an opportunity to a build
            candidate.
          </p>
        </div>
        <Badge tone={confirmed.tone}>Confirmed: {confirmed.label}</Badge>
      </div>
      <label className="block">
        <span className="text-sm font-semibold text-muted">Decision state</span>
        <Select
          className="mt-2"
          value={draftState}
          onChange={(event) => {
            clearMutationFeedback();
            setDraftState(event.target.value as ReviewState);
          }}
        >
          {REVIEW_STATE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </label>
      <label className="block">
        <span className="text-sm font-semibold text-muted">
          Local review note
        </span>
        <Textarea
          aria-label="Local review note"
          className="mt-2"
          maxLength={1000}
          value={draftNote}
          onChange={(event) => {
            clearMutationFeedback();
            setDraftNote(event.target.value);
          }}
        />
        <span className="mt-1 flex justify-between text-xs text-muted">
          <span>Excluded from exports.</span>
          <span>{draftNote.length}/1000</span>
        </span>
      </label>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {decisionUpdatedAt ? (
            <>
              Last decision update:{" "}
              <time dateTime={decisionUpdatedAt}>
                {new Date(decisionUpdatedAt).toLocaleString()}
              </time>
            </>
          ) : (
            "No decision saved yet."
          )}
        </p>
        <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>
          Save decision
        </Button>
      </div>
      {mutation.error ? (
        <StateMessage tone="danger" title="Decision was not saved">
          {apiErrorMessage(mutation.error)}
        </StateMessage>
      ) : null}
      {mutation.isSuccess ? (
        <StateMessage tone="success" title="Decision saved" />
      ) : null}
    </Card>
  );
}
