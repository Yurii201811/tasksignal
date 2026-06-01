# Model Card

## Model

Default embedding model: `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions.

The app loads the model with local-only behavior. If the model is not available locally, TaskSignal uses deterministic fallback vectors so the fixture demo and CI do not depend on downloads.

## Detector

The MVP detector is rule-based. It looks for:

- pain phrases
- repetition/manual-work phrases
- tool request phrases
- buying intent phrases
- concrete workflow hints

## Limitations

- Rule-based detection can miss subtle or sarcastic posts.
- Fallback embeddings are lower quality than sentence-transformer embeddings.
- Thematic fallback clustering is the default path; optional DBSCAN can be enabled with `TASKSIGNAL_USE_SKLEARN_CLUSTERING=1` and is tuned for the small demo dataset.
- Public discussion data can overrepresent loud complaints.

## Bias And Failure Modes

TaskSignal can overweight communities that post more frequently, English-language sources, and technical audiences. It should not be treated as market validation by itself.

## Evaluation Plan

Add labeled examples, train a logistic regression classifier in the notebooks, track precision/recall/F1, and compare cluster quality against human labels.

