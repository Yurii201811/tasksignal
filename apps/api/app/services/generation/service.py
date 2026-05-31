from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.scoring.service import SCORE_COMPONENTS

THEME_COPY = {
    "AI-generated code": {
        "target": "Developers and team leads adopting AI coding assistants",
        "workaround": "Manual PR review, scattered checklists, and ad hoc searches through generated diffs.",
        "mvp": "A GitHub repo scanner that flags missing tests, duplicated logic, fragile error handling, and suspicious generated code patterns.",
        "why": "AI coding assistants are now common, but teams still need a second-pass quality layer before shipping.",
    },
    "lead and community": {
        "target": "Early-stage SaaS founders and developer advocates",
        "workaround": "Manually searching Reddit, Hacker News, and forums, then guessing which posts deserve a reply.",
        "mvp": "A source-aware inbox that ranks public posts by relevance, pain intensity, buying intent, and safe reply timing.",
        "why": "Small teams want demand signals without paying for noisy enterprise social listening tools.",
    },
    "onboarding": {
        "target": "Small SaaS teams without dedicated analytics engineers",
        "workaround": "Exporting events to spreadsheets and manually inspecting where new users disappear.",
        "mvp": "A lightweight event import and funnel explainer that highlights the first confusing step and suggests experiments.",
        "why": "PLG teams need activation insight, but many analytics stacks are too heavy for early products.",
    },
    "GitHub Actions": {
        "target": "Developers maintaining CI workflows",
        "workaround": "Copying noisy CI logs into search, rereading YAML, and rerunning jobs to guess the root cause.",
        "mvp": "A CI log summarizer and workflow linter that identifies likely YAML mistakes, dependency failures, and next fixes.",
        "why": "Every team depends on CI, and AI-generated YAML has increased subtle workflow breakage.",
    },
    "spreadsheet-to-client-report": {
        "target": "Operators, agencies, freelancers, and finance-adjacent teams",
        "workaround": "Exporting CSVs, cleaning spreadsheet rows, and rebuilding client reports every week.",
        "mvp": "A CSV-to-report workflow builder with reusable transforms, checks, and branded Markdown/PDF output.",
        "why": "More small teams are expected to send polished recurring reports without hiring operations engineers.",
    },
}


def choose_theme(title: str) -> dict:
    for key, copy in THEME_COPY.items():
        if key.lower() in title.lower():
            return copy
    return {
        "target": "Builders and operators dealing with repetitive manual workflows",
        "workaround": "Manual copy-paste, spreadsheets, checklists, and scattered scripts.",
        "mvp": "A focused automation dashboard that ingests the repeated input, validates it, and exports the required output.",
        "why": "Teams are looking for small, reliable automation tools instead of broad platforms.",
    }


def common_phrases(items: list[dict]) -> list[str]:
    words: Counter[str] = Counter()
    stop = {"the", "and", "that", "with", "this", "into", "from", "every", "manually", "there"}
    for item in items:
        for token in f"{item['title']} {item['body']}".lower().replace("-", " ").split():
            cleaned = token.strip(".,!?():;\"'")
            if len(cleaned) > 4 and cleaned not in stop:
                words[cleaned] += 1
    return [word for word, _ in words.most_common(8)]


def percent(value: float | int | None) -> int:
    return round(float(value or 0) * 100)


def clean_excerpt(value: Any, max_length: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def evidence_excerpt(item: dict) -> str:
    spans = item.get("evidence_spans") or []
    if spans:
        return clean_excerpt(spans[0])
    return clean_excerpt(item.get("body"))


def evidence_pack(items: list[dict], limit: int = 4) -> str:
    ranked = sorted(
        items,
        key=lambda item: (
            item.get("pain_score", 0),
            item.get("task_concreteness_score", 0),
            item.get("buying_intent_score", 0),
        ),
        reverse=True,
    )
    bullets = []
    for index, item in enumerate(ranked[:limit], start=1):
        title = clean_excerpt(item.get("title"), 96)
        source = item.get("source", "fixture")
        signal_type = str(item.get("signal_type", "problem_signal")).replace("_", " ")
        url = item.get("url")
        source_line = f"\n   - Source: {url}" if url else ""
        bullets.append(
            f"{index}. [{source}] {title}\n"
            f'   - Evidence: "{evidence_excerpt(item)}"\n'
            f"   - Signal: {signal_type}. Scores: pain {percent(item.get('pain_score'))}, "
            f"task {percent(item.get('task_concreteness_score'))}, "
            f"buying {percent(item.get('buying_intent_score'))}.{source_line}"
        )
    return "\n".join(bullets)


def scoring_rationale(score: dict) -> str:
    lines = []
    for key, label, weight in SCORE_COMPONENTS:
        raw = float(score.get(key, 0))
        contribution = raw * weight * 100
        lines.append(
            f"- {label}: {percent(raw)}/100 raw, {abs(weight) * 100:.0f}% "
            f"{'penalty' if weight < 0 else 'weight'}, {contribution:+.1f} weighted points."
        )
    return "\n".join(lines)


def generate_codex_prompt(
    title: str,
    fields: dict,
    score: dict,
    evidence_summary: str,
    evidence_items: list[dict] | None = None,
) -> str:
    project_name = (
        title.split(" needs ")[0]
        .replace("Developers", "Code teams")
        .replace("Operators", "Ops teams")
    )
    evidence_items = evidence_items or []
    excerpts = (
        evidence_pack(evidence_items) if evidence_items else "- No source excerpts were available."
    )
    return f"""# Build {project_name}

You are a senior full-stack engineer. Build a working MVP for {project_name}.

## Problem

{fields["problem_statement"]}

## Target user

{fields["target_user"]}

## Evidence

{evidence_summary}

Top source excerpts:

{excerpts}

## Ranking rationale

Opportunity score: {percent(score["opportunity_score"])}/100.

{scoring_rationale(score)}

Interpretation: {score["explanation"]}

## MVP scope

- Ingest or import the repeated workflow data.
- Detect the risky, slow, or repetitive steps.
- Show a ranked dashboard with evidence and recommended next actions.
- Export a practical report or implementation artifact.

## Trust and privacy constraints

- Keep the local fixture demo working without paid services or live credentials.
- Store author hashes or omit author identity by default.
- Preserve source URLs and evidence excerpts so reviewers can audit why items were ranked.
- Make scoring visible enough that a first-time user can challenge the recommendation.
- Avoid spam, harassment, or bulk outreach workflows.

## Non-goals

- Do not build a generic productivity suite.
- Do not require paid AI APIs for the local demo.
- Do not collect unnecessary personal data.

## Recommended architecture

Frontend app, FastAPI backend, Postgres database, background processing worker, deterministic local summarization, and optional LLM enhancement behind environment variables.

## Tech stack

Next.js, TypeScript, Tailwind CSS, FastAPI, SQLAlchemy, PostgreSQL, pytest, and Docker Compose.

## Database schema

Core tables: sources, raw_items, normalized_items, signals, clusters, opportunities, exports, and audit logs.

## API endpoints

- GET /health
- POST /api/import
- POST /api/process
- GET /api/opportunities
- GET /api/opportunities/{{id}}
- GET /api/opportunities/{{id}}/export.md

## UI pages

- Dashboard with opportunity ranking
- Detail page with evidence and scoring
- Export page for report or prompt output
- Settings page for connectors and local model status

## Core user flow

User imports data, processes it, reviews ranked opportunities, opens the strongest opportunity, inspects the evidence, and exports a build-ready artifact.

## Acceptance criteria

- The app runs locally with fixture data.
- The main workflow works without paid credentials.
- Evidence, scoring, and generated output are visible.
- Exported Markdown is useful without manual cleanup.

## Tests

Add unit tests for ingestion, scoring, generation, and API health. Add a smoke test for the main dashboard workflow.

## Documentation

Document quickstart, architecture, privacy defaults, model limitations, and deployment options.

## Deployment

Use Docker Compose locally. Deploy frontend to Vercel, backend to Render or Hugging Face Spaces, and database to Supabase Postgres.

## Implementation instruction

Build a real working MVP. Do not create only stubs. Make reasonable decisions. Prioritize a functioning local demo. Do not ask unnecessary questions unless truly blocked.
"""


def generate_opportunity(title: str, summary: str, items: list[dict], score: dict) -> dict:
    theme = choose_theme(title)
    phrases = common_phrases(items)
    evidence_summary = (
        f"{len(items)} related complaints from {', '.join(sorted({item['source'] for item in items}))}. "
        f"Common phrases: {', '.join(phrases[:5])}."
    )
    fields = {
        "title": title,
        "problem_statement": f"{summary} People repeatedly describe this as concrete work that consumes time and creates avoidable mistakes.",
        "target_user": theme["target"],
        "current_workaround": theme["workaround"],
        "suggested_mvp": theme["mvp"],
        "why_now": theme["why"],
        "feasibility_score": score["feasibility"],
        "opportunity_score": score["opportunity_score"],
        "competition_notes": (
            "Focused workflow automation has room to differentiate; avoid turning it into a generic platform."
            if score["competition_penalty"] < 0.3
            else "The category is crowded, so the MVP needs a sharp niche and clear evidence trail."
        ),
    }
    fields["generated_prompt"] = generate_codex_prompt(
        title, fields, score, evidence_summary, items
    )
    fields["common_phrases"] = phrases
    return fields
