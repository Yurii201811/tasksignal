from __future__ import annotations

from datetime import UTC, datetime
from secrets import compare_digest
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.all_models import (
    Cluster,
    ClusterItem,
    ItemEmbedding,
    ItemSignal,
    Label,
    NormalizedItem,
    Opportunity,
    ScanJob,
    Source,
)
from app.schemas.api import (
    ItemOut,
    LabelCreate,
    OpportunityOut,
    ProcessSummary,
    ScanCreate,
    ScanOut,
    SearchRequest,
    SourceCreate,
    SourceOut,
)
from app.services.embeddings.service import EmbeddingService, cosine_similarity
from app.services.generation.service import generate_opportunity
from app.services.ingestion.normalization import safe_source_url
from app.services.scoring.service import score_opportunity
from app.workers.demo_pipeline import ensure_sources, process_demo, stats
from app.workers.scan_pipeline import CONNECTOR_FACTORIES, canonical_source, process_scan

router = APIRouter(prefix="/api")

PUBLIC_SCAN_API_SOURCES = {"fixture", "hackernews"}


def configured_public_scan_sources() -> set[str]:
    configured = settings.public_scan_sources.strip()
    if not configured or configured == "*":
        return set(PUBLIC_SCAN_API_SOURCES)

    requested_sources = {
        canonical_source(source) for source in configured.split(",") if source.strip()
    }
    return requested_sources & PUBLIC_SCAN_API_SOURCES


def public_scan_source(source: str) -> str:
    source_type = canonical_source(source)
    if source_type not in CONNECTOR_FACTORIES:
        supported = ", ".join(sorted(CONNECTOR_FACTORIES))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source '{source}'. Supported sources: {supported}.",
        )

    allowed_sources = configured_public_scan_sources()
    if source_type not in allowed_sources:
        allowed = ", ".join(sorted(allowed_sources))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Source '{source}' is not enabled for this deployment. Allowed sources: {allowed}."
            ),
        )
    return source_type


def item_to_out(item: NormalizedItem, signal: ItemSignal | None = None) -> ItemOut:
    return ItemOut(
        id=item.id,
        source=item.source,
        external_id=item.external_id,
        url=item.url,
        title=item.title,
        body=item.body,
        score=item.score,
        comments_count=item.comments_count,
        created_at=item.created_at,
        tags=item.tags,
        signal_type=signal.signal_type if signal else None,
        pain_score=signal.pain_score if signal else None,
        task_concreteness_score=signal.task_concreteness_score if signal else None,
        buying_intent_score=signal.buying_intent_score if signal else None,
        evidence_spans=signal.evidence_spans_json if signal else [],
    )


def opportunity_to_out(db: Session, opportunity: Opportunity) -> OpportunityOut:
    rows = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id)
        .where(ClusterItem.cluster_id == opportunity.cluster_id)
        .order_by(
            ItemSignal.pain_score.desc(),
            ItemSignal.task_concreteness_score.desc(),
            NormalizedItem.created_at.desc(),
        )
    ).all()
    evidence = [item_to_out(item, signal) for item, signal in rows]
    top_source = max(
        {item.source for item, _ in rows},
        key=lambda s: sum(1 for item, _ in rows if item.source == s),
        default="fixture",
    )
    return OpportunityOut(
        **{
            column.name: getattr(opportunity, column.name)
            for column in Opportunity.__table__.columns
        },
        evidence_items=evidence,
        signal_count=len(evidence),
        top_source=top_source,
    )


def cluster_signal_rows(db: Session, cluster_id: UUID) -> list[tuple[NormalizedItem, ItemSignal]]:
    return list(
        db.execute(
            select(NormalizedItem, ItemSignal)
            .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
            .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id)
            .where(ClusterItem.cluster_id == cluster_id)
            .order_by(
                ItemSignal.pain_score.desc(),
                ItemSignal.task_concreteness_score.desc(),
                NormalizedItem.created_at.desc(),
            )
        ).all()
    )


def row_to_generation_item(item: NormalizedItem, signal: ItemSignal) -> dict:
    return {
        "id": item.id,
        "source": item.source,
        "url": item.url,
        "title": item.title,
        "body": item.body,
        "created_at": item.created_at,
        "signal_type": signal.signal_type,
        "pain_score": signal.pain_score,
        "task_concreteness_score": signal.task_concreteness_score,
        "buying_intent_score": signal.buying_intent_score,
        "evidence_spans": signal.evidence_spans_json,
    }


def markdown_value(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def evidence_excerpt(item: ItemOut) -> str:
    spans = [markdown_value(span) for span in item.evidence_spans if markdown_value(span)]
    if spans:
        return spans[0]
    fallback = markdown_value(item.body or item.title)
    return f"{fallback[:237].rstrip()}..." if len(fallback) > 240 else fallback


def evidence_source_url(item: ItemOut) -> str:
    return safe_source_url(item.url, fallback="No source URL stored")


def evidence_bundle_markdown(opportunity: OpportunityOut) -> str:
    breakdown = opportunity.scoring_breakdown_json
    score_rows = [
        ("Frequency", breakdown.get("frequency")),
        ("Recency", breakdown.get("recency")),
        ("Pain intensity", breakdown.get("pain_intensity")),
        ("Task concreteness", breakdown.get("task_concreteness")),
        ("Buying intent", breakdown.get("buying_intent")),
        ("Feasibility", breakdown.get("feasibility")),
        ("Competition penalty", breakdown.get("competition_penalty")),
        ("Opportunity score", opportunity.opportunity_score),
    ]
    lines = [
        f"# Evidence Bundle: {markdown_value(opportunity.title)}",
        "",
        "## Opportunity",
        "",
        f"- Problem: {markdown_value(opportunity.problem_statement)}",
        f"- Target user: {markdown_value(opportunity.target_user)}",
        f"- Current workaround: {markdown_value(opportunity.current_workaround)}",
        f"- Suggested MVP: {markdown_value(opportunity.suggested_mvp)}",
        f"- Why now: {markdown_value(opportunity.why_now)}",
        f"- Competition notes: {markdown_value(opportunity.competition_notes)}",
        f"- Generated prompt: /api/opportunities/{opportunity.id}/prompt",
        "",
        "## Score Breakdown",
        "",
    ]

    for label, value in score_rows:
        if isinstance(value, (int, float)):
            lines.append(f"- {label}: {value:.3f}")

    rank_drivers = breakdown.get("rank_drivers")
    if isinstance(rank_drivers, list) and rank_drivers:
        lines.extend(["", "## Rank Drivers", ""])
        for driver in rank_drivers:
            lines.append(f"- {markdown_value(driver)}")

    lines.extend(
        [
            "",
            "## Evidence Items",
            "",
        ]
    )
    if not opportunity.evidence_items:
        lines.append("- No evidence items were returned for this opportunity.")

    for index, item in enumerate(opportunity.evidence_items, start=1):
        lines.extend(
            [
                f"### {index}. {markdown_value(item.title)}",
                "",
                f"- Source: {markdown_value(item.source)}",
                f"- URL: {evidence_source_url(item)}",
                f"- Signal type: {markdown_value(item.signal_type or 'unknown')}",
            ]
        )
        if item.pain_score is not None:
            lines.append(f"- Pain score: {item.pain_score:.3f}")
        if item.task_concreteness_score is not None:
            lines.append(f"- Task concreteness score: {item.task_concreteness_score:.3f}")
        if item.buying_intent_score is not None:
            lines.append(f"- Buying intent score: {item.buying_intent_score:.3f}")
        lines.extend(["", "Evidence excerpt:", "", f"> {evidence_excerpt(item)}", ""])

    lines.extend(
        [
            "## Caveats",
            "",
            "- This bundle is generated from public-source normalized items and detector spans.",
            "- Raw usernames, author hashes, credential fields, and raw connector payloads are omitted.",
            "- Scores are heuristic review aids, not proof of demand or adoption.",
            "- Source URLs are preserved when available so reviewers can audit the evidence trail.",
            "",
        ]
    )
    return "\n".join(lines)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)) -> dict:
    return stats(db)


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)) -> list[Source]:
    ensure_sources(db)
    return list(db.scalars(select(Source)).all())


@router.post("/sources", response_model=SourceOut)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> Source:
    source = Source(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: UUID, payload: SourceCreate, db: Session = Depends(get_db)) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for key, value in payload.model_dump().items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}")
def delete_source(source_id: UUID, db: Session = Depends(get_db)) -> dict:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(source)
    db.commit()
    return {"deleted": True}


@router.post("/scans", response_model=ScanOut)
def create_scan(payload: ScanCreate, db: Session = Depends(get_db)) -> ScanJob:
    source_type = public_scan_source(payload.source)
    try:
        return process_scan(
            db,
            source=source_type,
            query=payload.query,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scans", response_model=list[ScanOut])
def list_scans(db: Session = Depends(get_db)) -> list[ScanJob]:
    return list(db.scalars(select(ScanJob).order_by(ScanJob.started_at.desc())).all())


@router.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: UUID, db: Session = Depends(get_db)) -> ScanJob:
    scan = db.get(ScanJob, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.get("/items", response_model=list[ItemOut])
def list_items(db: Session = Depends(get_db)) -> list[ItemOut]:
    rows = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id, isouter=True)
        .order_by(NormalizedItem.created_at.desc())
        .limit(100)
    ).all()
    return [item_to_out(item, signal) for item, signal in rows]


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: UUID, db: Session = Depends(get_db)) -> ItemOut:
    row = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id, isouter=True)
        .where(NormalizedItem.id == item_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item, signal = row
    return item_to_out(item, signal)


@router.post("/process/demo", response_model=ProcessSummary)
def run_demo(
    reset: bool = False,
    x_demo_reset_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    if reset and (
        not settings.demo_reset_token
        or x_demo_reset_token is None
        or not compare_digest(x_demo_reset_token, settings.demo_reset_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo reset requires a valid X-Demo-Reset-Token header",
        )
    return process_demo(db, reset=reset)


@router.post("/process/detect")
@router.post("/process/embed")
@router.post("/process/cluster")
@router.post("/process/generate-opportunities")
def process_stage() -> dict:
    return {"status": "available in the combined demo pipeline", "endpoint": "/api/process/demo"}


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(db: Session = Depends(get_db)) -> list[OpportunityOut]:
    opportunities = db.scalars(
        select(Opportunity).order_by(Opportunity.opportunity_score.desc())
    ).all()
    return [opportunity_to_out(db, opportunity) for opportunity in opportunities]


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(opportunity_id: UUID, db: Session = Depends(get_db)) -> OpportunityOut:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opportunity_to_out(db, opportunity)


@router.post("/opportunities/{opportunity_id}/regenerate", response_model=OpportunityOut)
def regenerate_opportunity(opportunity_id: UUID, db: Session = Depends(get_db)) -> OpportunityOut:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    rows = cluster_signal_rows(db, opportunity.cluster_id)
    if not rows:
        raise HTTPException(
            status_code=409, detail="Opportunity has no evidence to regenerate from"
        )

    generation_items = [row_to_generation_item(item, signal) for item, signal in rows]
    cluster = db.get(Cluster, opportunity.cluster_id)
    source_title = cluster.title if cluster else opportunity.title
    source_summary = cluster.summary if cluster else opportunity.problem_statement
    candidate_text = f"{source_title} {source_summary}"
    score = score_opportunity(generation_items, candidate_text)
    generated = generate_opportunity(source_title, source_summary, generation_items, score)

    opportunity.title = generated["title"]
    opportunity.problem_statement = generated["problem_statement"]
    opportunity.target_user = generated["target_user"]
    opportunity.current_workaround = generated["current_workaround"]
    opportunity.suggested_mvp = generated["suggested_mvp"]
    opportunity.why_now = generated["why_now"]
    opportunity.feasibility_score = generated["feasibility_score"]
    opportunity.opportunity_score = generated["opportunity_score"]
    opportunity.competition_notes = generated["competition_notes"]
    opportunity.scoring_breakdown_json = {**score, "common_phrases": generated["common_phrases"]}
    opportunity.generated_prompt = generated["generated_prompt"]
    opportunity.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(opportunity)
    return opportunity_to_out(db, opportunity)


@router.get("/opportunities/{opportunity_id}/prompt")
def get_prompt(opportunity_id: UUID, db: Session = Depends(get_db)) -> dict:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return {"prompt": opportunity.generated_prompt}


@router.get("/opportunities/{opportunity_id}/export.md")
def export_prompt(opportunity_id: UUID, db: Session = Depends(get_db)) -> Response:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return Response(
        opportunity.generated_prompt,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{opportunity_id}.md"'},
    )


@router.get("/opportunities/{opportunity_id}/evidence.md")
def export_evidence_bundle(opportunity_id: UUID, db: Session = Depends(get_db)) -> Response:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    bundle = evidence_bundle_markdown(opportunity_to_out(db, opportunity))
    return Response(
        bundle,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="evidence-{opportunity_id}.md"'
        },
    )


@router.post("/search/semantic")
def semantic_search(payload: SearchRequest, db: Session = Depends(get_db)) -> dict:
    embedder = EmbeddingService()
    query_vector = embedder.embed_texts([payload.query])[0]
    rows = db.execute(select(NormalizedItem, ItemEmbedding).join(ItemEmbedding)).all()
    ranked = sorted(
        [
            {
                "item": item_to_out(item).model_dump(mode="json"),
                "similarity": round(cosine_similarity(query_vector, embedding.embedding), 3),
            }
            for item, embedding in rows
        ],
        key=lambda entry: entry["similarity"],
        reverse=True,
    )
    return {"items": ranked[: payload.limit], "opportunities": []}


@router.post("/labels")
def create_label(payload: LabelCreate, db: Session = Depends(get_db)) -> dict:
    label = Label(**payload.model_dump())
    db.add(label)
    db.commit()
    return {"id": label.id, "created": True}
