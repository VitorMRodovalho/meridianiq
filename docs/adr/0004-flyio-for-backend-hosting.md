# 0004. Fly.io for backend hosting

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-17 (retroactive — decision made circa v0.6, 2024)

## Context and Problem Statement

The FastAPI backend (ADR-0001) needs to be hosted somewhere:
- Accessible as an HTTPS API from the SvelteKit frontend on Cloudflare Pages (see ADR-0002).
- Able to run Python 3.13 with native system deps (WeasyPrint needs `libpango` + `libcairo`; pyiceberg needs specific Python versions).
- Free-tier eligible for the pre-revenue phase.
- Fast deploy loop (maintainer iterates frequently).
- Predictable cost curve as traffic grows.
- Deployable via a `Dockerfile` so local dev and production match exactly.

## Decision Drivers

- **Docker-first** — the app has system deps (WeasyPrint + libpango + libcairo) that are easier to manage through a Dockerfile than through a platform's magic buildpack.
- **Free / low-cost tier** sufficient for pre-revenue.
- **Zero-to-deployed in minutes** — solo dev; friction on the deploy path compounds into never shipping.
- **Cold-start tolerable** — a few seconds is fine; tens of seconds is not.
- **Secrets management** — needed `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, etc. without a separate vault product.

## Considered Options

1. **Fly.io** — Docker-first, edge-deployed, generous free tier.
2. **Render** — Docker-supported, auto-deploy from GitHub.
3. **Railway** — Docker-friendly, modern UX, per-second pricing.
4. **AWS Fargate / ECS** — full control, but substantial setup cost.
5. **Google Cloud Run** — Docker-first, fast scale-to-zero.
6. **Heroku** — incumbent, but buildpack model + pricing shifted post-2022.

## Decision Outcome

**Chosen: Fly.io.**

### Rationale

- **Dockerfile-native** — `fly launch` reads the Dockerfile directly. No buildpack translation, no "Fly knows Python better than you" surprises.
- **Edge placement** — the app runs in a region close to Supabase (sa-east-ish) and to the Cloudflare Pages frontend. Latency profile is solid for a SaaS-grade API.
- **Machines model** — Fly's v2 Machines primitive is simpler than Nomad/K8s but more transparent than Cloud Run. `flyctl status` tells you exactly what's running.
- **Free tier** covers one `shared-cpu-1x` machine with 256 MB RAM; enough for pre-revenue traffic.
- **Secrets CLI** — `fly secrets set` is one command, no separate vault product.
- **Health checks + autoscale** defined inline in `fly.toml` — no AWS-style sprawl of console settings.

### Rejected alternatives

- **Render** — comparable on features but free tier is more limited and builds are slower in our experience. Reasonable second choice.
- **Railway** — good UX but the pricing started to bite for a project that wants to run at $0 while validating the market. Also historically had more deploy-pipeline flakiness than Fly.io.
- **AWS Fargate / ECS** — far more ceremony. Task definitions, VPCs, ALBs, target groups, IAM roles — a whole week of setup to get where `fly launch` takes 10 minutes. Worth it only if AWS-native integrations (SQS, Lambda, Secrets Manager) were load-bearing. They aren't.
- **Google Cloud Run** — attractive scale-to-zero, but cold start on a multi-hundred-MB container with WeasyPrint deps was 5–10 seconds. Also more billing surface than Fly's single machine.
- **Heroku** — post-2022 the free dyno was removed and the pricing model became punitive for hobby-class projects. The buildpack model also fights with our Dockerfile needs.

## Consequences

**Positive**:
- Deploy via `fly deploy` takes 90–120 seconds; the loop is fast enough that the maintainer actually deploys.
- Dockerfile is the single source of truth for runtime. Local `docker compose up meridianiq-api` matches production byte-for-byte.
- Secrets are one `fly secrets set` per env var; configuration is in `fly.toml`, versioned with the code.

**Negative**:
- **Cold start ~10s** on the free-tier single machine when no traffic has hit in a while. This causes 502 + CORS error on the first request (documented as BUG-007). Frontend handles the symptom by retrying, but a first-time user sees a latency spike.
- **Single-region by default** — horizontal expansion requires explicit `fly scale count` and paying attention to region placement.
- **Fewer managed extras than AWS** — no native message queue, no Lambda triggers, no SQS. For a single-service synchronous API this is fine; if the architecture grows event-driven, we'd need to add a queue (Supabase Edge Functions or SQS).

**Neutral**:
- The Dockerfile pins Python to 3.13-slim because pyiceberg does not yet publish a 3.14 wheel (see CLAUDE.md). The CI pipeline runs on 3.14; the Dockerfile on 3.13. That split is a known drift point and will close once pyiceberg catches up.
