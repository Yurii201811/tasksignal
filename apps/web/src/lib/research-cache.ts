import type { QueryClient } from "@tanstack/react-query";

/** A review changes readiness and decisions on both snapshot and thread views. */
export async function refreshReviewQueries(client: QueryClient) {
  await Promise.all(
    [
      "opportunity",
      "opportunities",
      "opportunity-thread",
      "opportunity-threads",
      "evaluation",
      "readiness",
    ].map((key) => client.invalidateQueries({ queryKey: [key] })),
  );
}
