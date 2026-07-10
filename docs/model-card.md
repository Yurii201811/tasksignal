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

## Human Evaluation

TaskSignal reports coverage over evidence linked to generated opportunities and precision on manually reviewed predicted-positive evidence: `true_signal / (true_signal + false_positive)`. Reviews are selected by the operator, so the report is subject to selection bias and does not represent all detected or undetected items. Recall and F1 are not reported because v0.2 has no reviewed predicted-negative or undetected examples from which to estimate false negatives and recall.
