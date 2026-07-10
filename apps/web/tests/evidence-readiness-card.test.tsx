import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceReadinessCard } from "../src/features/evidence-readiness-card";

describe("EvidenceReadinessCard", () => {
  it("renders backend checks and a sensitive-risk gap without confidence copy", () => {
    render(
      <EvidenceReadinessCard
        readiness={{
          level: "weak",
          evidence_count: 5,
          source_count: 2,
          safe_url_count: 4,
          reviewed_count: 3,
          source_url_coverage: 0.8,
          human_review_coverage: 0.6,
          checks: {
            enough_evidence: true,
            source_diversity: true,
            source_url_coverage: true,
            human_review_coverage: true,
          },
          passed_checks: [
            "enough_evidence",
            "source_diversity",
            "source_url_coverage",
            "human_review_coverage",
          ],
          gaps: [
            "Resolve or exclude evidence marked sensitive risk before advancing.",
          ],
        }}
      />,
    );

    expect(screen.getByText("Evidence readiness")).toBeInTheDocument();
    expect(screen.getByText("Safe source URL coverage")).toBeInTheDocument();
    expect(screen.getByText(/sensitive risk/)).toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
  });
});
