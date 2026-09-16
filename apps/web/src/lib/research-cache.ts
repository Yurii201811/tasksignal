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

/**
 * A project run adds a scan, evidence, and possibly snapshots, so every list
 * and total that summarizes research output must refresh. When the project is
 * known, its own history and comparison caches refresh too; otherwise (run-due
 * can touch any project) every per-project cache is refreshed.
 */
export async function refreshProjectRunQueries(
  client: QueryClient,
  projectId?: string,
) {
  const shared = [
    "research-projects",
    "scans",
    "stats",
    "opportunities",
    "opportunity-threads",
    "readiness",
    "evaluation",
  ].map((key) => client.invalidateQueries({ queryKey: [key] }));
  const perProject = [
    "research-project",
    "research-project-runs",
    "research-project-run-delta",
  ].map((key) =>
    client.invalidateQueries({
      queryKey: projectId ? [key, projectId] : [key],
    }),
  );
  await Promise.all([...shared, ...perProject]);
}
