# ADR 0001: Local-First Full-Stack Architecture

TaskSignal uses Next.js for the dashboard, FastAPI for API and pipeline orchestration, and PostgreSQL with pgvector for production storage. The MVP also supports SQLite for tests and local CI convenience.

This keeps the portfolio project realistic while preserving a no-key demo path.

