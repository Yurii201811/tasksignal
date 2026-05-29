from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.all_models import (
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
    ScanOut,
    SearchRequest,
    SourceCreate,
    SourceOut,
)
from app.services.embeddings.service import EmbeddingService, cosine_similarity
from app.workers.demo_pipeline import ensure_sources, process_demo, stats

router = APIRouter(prefix="/api")


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
    ).all()
    evidence = [item_to_out(item, signal) for item, signal in rows]
    top_source = max({item.source for item, _ in rows}, key=lambda s: sum(1 for item, _ in rows if item.source == s), default="fixture")
    return OpportunityOut(
        **{column.name: getattr(opportunity, column.name) for column in Opportunity.__table__.columns},
        evidence_items=evidence,
        signal_count=len(evidence),
        top_source=top_source,
    )


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
def create_scan(db: Session = Depends(get_db)) -> ScanJob:
    job = ScanJob(status="queued", query="manual scan placeholder")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


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
def run_demo(reset: bool = True, db: Session = Depends(get_db)) -> dict[str, int]:
    return process_demo(db, reset=reset)


@router.post("/process/detect")
@router.post("/process/embed")
@router.post("/process/cluster")
@router.post("/process/generate-opportunities")
def process_stage() -> dict:
    return {"status": "available in the combined demo pipeline", "endpoint": "/api/process/demo"}


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(db: Session = Depends(get_db)) -> list[OpportunityOut]:
    opportunities = db.scalars(select(Opportunity).order_by(Opportunity.opportunity_score.desc())).all()
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
    opportunity.updated_at = opportunity.updated_at
    db.commit()
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

