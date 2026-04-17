# 0003. Supabase for auth, database, and storage

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-17 (retroactive — decision made circa v0.6, 2024)

## Context and Problem Statement

MeridianIQ needs:
- **PostgreSQL** — the analysis engines rely on relational data (projects, activities, WBS, CBS, snapshots) with strong integrity.
- **Row-level security** — multi-tenant by ownership; a user should only see their own schedules.
- **OAuth auth** — Google + LinkedIn + Microsoft for construction-industry personas.
- **File storage** — XER files (~2–40 MB each), PDF reports.
- **Ability to run on the free tier** while the project was pre-revenue.
- **Runtime cost of ~$0/month** for the pre-revenue phase.

Building these four services ourselves would be months of backend work. Integrating four different SaaS products would multiply the moving parts.

## Decision Drivers

- **Single primitive** — one vendor for auth + DB + storage means one set of credentials, one mental model, one support channel.
- **PostgreSQL-first** — the queryable, extensible database we need; not a NoSQL alternative.
- **RLS at the database layer** — ownership is an invariant, not a per-endpoint check.
- **Free tier sufficient for pre-revenue** — $0/month until traction justifies the paid tier.
- **Exit-friendly** — Supabase is Postgres + GoTrue + Storage API, all of which are open source and could be self-hosted later without a rewrite.

## Considered Options

1. **Supabase**
2. **Firebase** (Firestore + Firebase Auth + Cloud Storage)
3. **Self-hosted Postgres + Auth0 + S3 + custom RLS**
4. **Amazon Aurora Serverless + Cognito + S3**
5. **PlanetScale + Clerk + S3**

## Decision Outcome

**Chosen: Supabase.**

### Rationale

- **PostgreSQL natively** — analysis queries use window functions, `jsonb`, CTEs; none of that works well on Firestore. MeridianIQ is query-heavy, not document-store-shaped.
- **RLS policies** are written once as SQL and enforced for every request regardless of which client hits the DB. This closes an entire class of authorisation bugs by construction.
- **GoTrue for OAuth** bundles Google / LinkedIn / Microsoft flows behind one JS SDK and one REST endpoint. We wrote zero OAuth glue.
- **Supabase Storage** is an S3-compatible bucket with RLS. Same policy language as the DB; same authorisation guarantees.
- **Free tier** covers pre-revenue comfortably and the pricing curve beyond is understandable.
- **ES256 JWTs** (see ADR-0005) are the default; that was actually a constraint we accepted *because* Supabase provides them — see that ADR for the JWT-algorithm discussion.

### Rejected alternatives

- **Firebase** — Firestore's document-query model is wrong for an analysis platform that runs `JOIN`-heavy reads. We'd either write against the wrong abstraction or adopt a second DB. Firebase Auth also has weaker OAuth-provider ergonomics for LinkedIn and Microsoft.
- **Self-hosted Postgres + Auth0 + S3** — probably the best "freedom" option, but three vendors to manage, three billing surfaces, and RLS would have to be wired manually at every endpoint. Six months of work we chose to defer.
- **Aurora Serverless + Cognito + S3** — AWS-native and production-grade, but pre-revenue free tier is stingy compared to Supabase. Cognito's OAuth flows are notoriously rough for LinkedIn.
- **PlanetScale + Clerk + S3** — PlanetScale is MySQL. The analysis code leans on Postgres-specific features (`jsonb`, LATERAL joins, window functions). Migration cost alone disqualified it.

## Consequences

**Positive**:
- 20 migrations in `supabase/migrations/` — all versioned, reviewable, and applied via the Supabase CLI.
- RLS policies mean every endpoint that reads from Supabase is authorised by the database itself, not by the FastAPI handler. Auth bugs become RLS bugs — fewer, better-localised, and easier to audit.
- One vendor lock-in surface instead of three. The OAuth story alone would have been weeks of work against Cognito/Clerk/Auth0.
- Supabase SDK's client abstraction (`supabase-py`) wrapped behind our `src/database/store.py` keeps us loosely coupled — we have `InMemoryStore` for tests, `SupabaseStore` for prod.

**Negative**:
- **Port 6543 (pooler) vs 5432** — the default connection string Supabase's dashboard shows is the pooler, and tooling that assumes 5432 needs to be reconfigured. Documented as a gotcha in `CLAUDE.md`.
- **Vendor dependency** — Supabase is our auth *and* DB *and* storage. If Supabase has a major outage, the whole app is down.
- **Pool size limits** on the free tier can bite under load; upgrading is straightforward but a cost consideration.

**Neutral**:
- Migration away from Supabase is possible but non-trivial. GoTrue is open-source; self-hosting would replicate auth. PostgreSQL itself is portable. Storage is S3-compatible. The RLS policies travel as SQL. So the exit path exists but requires deliberate effort — roughly one focused week.
