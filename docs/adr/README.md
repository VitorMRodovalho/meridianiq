# Architectural Decision Records

This directory captures the architectural decisions behind MeridianIQ, using the [MADR](https://adr.github.io/madr/) (Markdown Architectural Decision Records) format.

## Why ADRs

An ADR records the **context**, **decision**, and **consequences** of an architectural choice at the moment it was made. Reading the repository tells you *what* the codebase does; reading the ADR tells you *why* it does it that way — including the trade-offs we accepted and the options we rejected.

Medium-sized projects accumulate decisions quickly. Without ADRs, the reasoning behind "why FastAPI instead of Django?" or "why Fly.io instead of AWS?" lives only in commit messages and the maintainer's memory. Both decay.

## Index

| # | Title | Status |
|---|---|---|
| [0000](0000-record-architecture-decisions.md) | Record architecture decisions | accepted |
| [0001](0001-fastapi-for-backend.md) | FastAPI for the backend API | accepted |
| [0002](0002-sveltekit-for-frontend.md) | SvelteKit + Tailwind v4 for the frontend | accepted |
| [0003](0003-supabase-for-auth-db-storage.md) | Supabase for auth, database, and storage | accepted |
| [0004](0004-flyio-for-backend-hosting.md) | Fly.io for backend hosting | accepted |
| [0005](0005-es256-jwt-algorithm.md) | ES256 JWT algorithm with JWKS | accepted |

## Adding a new ADR

1. Copy the most recent ADR as a starting template, or use the MADR template at https://adr.github.io/madr/.
2. Number it next in sequence.
3. Keep the title short and declarative: "Use X for Y".
4. Fill in Context, Decision Drivers, Considered Options, Decision Outcome, Consequences.
5. Status starts as `proposed` during discussion, `accepted` after merge, and can later become `deprecated` or `superseded by ADR-XXXX`.
6. Add the row to the index above.
7. Link from relevant code/docs when the decision is load-bearing.

## Superseding

ADRs are **immutable** once accepted. To change a decision, write a new ADR that supersedes the old one. Update the old ADR's status to `superseded by ADR-XXXX` but leave its content intact — the history matters.
