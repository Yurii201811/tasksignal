from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import (
    Cluster,
    ItemSignal,
    NormalizedItem,
    Opportunity,
    ResearchProjectRun,
    ScanItem,
)


class IncompleteRunError(ValueError):
    """Raised when a run has no trustworthy complete lineage to compare."""


@dataclass(frozen=True)
class Observation:
    source: str
    external_id: str
    text_hash: str
    created_in_scan: bool

    @property
    def stable_identity(self) -> tuple[str, str]:
        return self.source, self.external_id


@dataclass(frozen=True)
class DeltaCounts:
    new: int
    seen_before: int
    updated: int
    unchanged: int
    not_observed_this_run: int


@dataclass(frozen=True)
class GeneratedSnapshots:
    clusters: int
    opportunities: int


@dataclass(frozen=True)
class OpportunityThreadChanges:
    new: int
    updated: int
    unchanged: int
    not_observed_this_run: int


@dataclass(frozen=True)
class RunDelta:
    project_id: UUID
    run_id: UUID
    scan_id: UUID
    sequence: int
    previous_run_id: UUID | None
    evidence_changes: DeltaCounts
    signal_changes: DeltaCounts
    generated_snapshots: GeneratedSnapshots
    opportunity_changes: OpportunityThreadChanges


def list_project_runs(db: Session, project_id: UUID) -> list[ResearchProjectRun]:
    return list(
        db.scalars(
            select(ResearchProjectRun)
            .where(ResearchProjectRun.project_id == project_id)
            .order_by(ResearchProjectRun.sequence.desc())
        ).all()
    )


def get_project_run(
    db: Session,
    project_id: UUID,
    run_id: UUID,
) -> ResearchProjectRun | None:
    return db.scalar(
        select(ResearchProjectRun).where(
            ResearchProjectRun.id == run_id,
            ResearchProjectRun.project_id == project_id,
        )
    )


def observations_for_scan(
    db: Session,
    scan_id: UUID,
    *,
    signals_only: bool,
) -> list[Observation]:
    statement = (
        select(
            NormalizedItem.source,
            NormalizedItem.external_id,
            NormalizedItem.text_hash,
            ScanItem.created_in_scan,
        )
        .join(ScanItem, ScanItem.item_id == NormalizedItem.id)
        .where(ScanItem.scan_id == scan_id)
    )
    if signals_only:
        statement = statement.where(
            select(ItemSignal.id)
            .where(
                ItemSignal.item_id == NormalizedItem.id,
                ItemSignal.is_problem_signal.is_(True),
            )
            .exists()
        )
    return [Observation(*row) for row in db.execute(statement).all()]


def change_counts(
    current: list[Observation],
    previous: list[Observation],
) -> DeltaCounts:
    current_by_identity: dict[tuple[str, str], set[str]] = defaultdict(set)
    previous_by_identity: dict[tuple[str, str], set[str]] = defaultdict(set)
    for entry in current:
        current_by_identity[entry.stable_identity].add(entry.text_hash)
    for entry in previous:
        previous_by_identity[entry.stable_identity].add(entry.text_hash)

    shared_identities = current_by_identity.keys() & previous_by_identity.keys()
    updated = sum(
        current_by_identity[identity] != previous_by_identity[identity]
        for identity in shared_identities
    )
    unchanged = sum(
        current_by_identity[identity] == previous_by_identity[identity]
        for identity in shared_identities
    )
    return DeltaCounts(
        new=sum(entry.created_in_scan for entry in current),
        seen_before=sum(not entry.created_in_scan for entry in current),
        updated=updated,
        unchanged=unchanged,
        not_observed_this_run=len(previous_by_identity.keys() - current_by_identity.keys()),
    )


def calculate_run_delta(db: Session, run: ResearchProjectRun) -> RunDelta:
    if not run.lineage_complete or run.scan.status != "completed":
        raise IncompleteRunError("Run lineage is incomplete and cannot be compared safely.")

    prior_runs = list(
        db.scalars(
            select(ResearchProjectRun)
            .where(
                ResearchProjectRun.project_id == run.project_id,
                ResearchProjectRun.sequence < run.sequence,
                ResearchProjectRun.lineage_complete.is_(True),
            )
            .order_by(ResearchProjectRun.sequence.desc())
        ).all()
    )
    previous_run = prior_runs[0] if prior_runs else None

    current_evidence = observations_for_scan(db, run.scan_id, signals_only=False)
    current_signals = observations_for_scan(db, run.scan_id, signals_only=True)
    previous_evidence = (
        observations_for_scan(db, previous_run.scan_id, signals_only=False)
        if previous_run
        else []
    )
    previous_signals = (
        observations_for_scan(db, previous_run.scan_id, signals_only=True)
        if previous_run
        else []
    )
    cluster_count = db.scalar(
        select(func.count()).select_from(Cluster).where(Cluster.scan_id == run.scan_id)
    )
    opportunity_count = db.scalar(
        select(func.count())
        .select_from(Opportunity)
        .where(Opportunity.scan_id == run.scan_id)
    )
    current_thread_content = {
        thread_id: snapshot_content_hash
        for thread_id, snapshot_content_hash in db.execute(
            select(Opportunity.thread_id, Opportunity.content_hash).where(
                Opportunity.run_id == run.id
            )
        ).all()
    }
    previous_thread_content = (
        {
            thread_id: snapshot_content_hash
            for thread_id, snapshot_content_hash in db.execute(
                select(Opportunity.thread_id, Opportunity.content_hash).where(
                    Opportunity.run_id == previous_run.id
                )
            ).all()
        }
        if previous_run
        else {}
    )
    prior_thread_content: dict[UUID, str] = {}
    for prior_run in reversed(prior_runs):
        prior_thread_content.update(
            {
                thread_id: snapshot_content_hash
                for thread_id, snapshot_content_hash in db.execute(
                    select(Opportunity.thread_id, Opportunity.content_hash).where(
                        Opportunity.run_id == prior_run.id
                    )
                ).all()
            }
        )
    new_threads = current_thread_content.keys() - prior_thread_content.keys()
    existing_threads = current_thread_content.keys() & prior_thread_content.keys()
    thread_changes = OpportunityThreadChanges(
        new=len(new_threads),
        updated=sum(
            current_thread_content[thread_id] != prior_thread_content[thread_id]
            for thread_id in existing_threads
        ),
        unchanged=sum(
            current_thread_content[thread_id] == prior_thread_content[thread_id]
            for thread_id in existing_threads
        ),
        not_observed_this_run=len(
            previous_thread_content.keys() - current_thread_content.keys()
        ),
    )
    return RunDelta(
        project_id=run.project_id,
        run_id=run.id,
        scan_id=run.scan_id,
        sequence=run.sequence,
        previous_run_id=previous_run.id if previous_run else None,
        evidence_changes=change_counts(current_evidence, previous_evidence),
        signal_changes=change_counts(current_signals, previous_signals),
        generated_snapshots=GeneratedSnapshots(
            clusters=cluster_count or 0,
            opportunities=opportunity_count or 0,
        ),
        opportunity_changes=thread_changes,
    )
