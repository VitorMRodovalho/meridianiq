# 0005. ES256 JWT algorithm with JWKS

* Status: accepted
* Deciders: @VitorMRodovalho
* Date: 2026-04-17 (retroactive — decision made circa v0.7, 2024)

## Context and Problem Statement

MeridianIQ's auth model (ADR-0003) uses Supabase Auth for OAuth. Supabase issues JSON Web Tokens (JWTs) to authenticated clients, and our FastAPI backend needs to verify those tokens on every protected request.

There are three families of signing algorithms in common use:
- **HMAC-based** (HS256, HS384, HS512) — shared symmetric secret.
- **RSA-based** (RS256, RS384, RS512) — asymmetric key pair.
- **ECDSA-based** (ES256, ES384, ES512) — asymmetric elliptic-curve key pair.

Supabase defaults to **ES256** in current deployments (older projects used HS256 when the Supabase JWT secret was shared out-of-band). We needed to commit to one verification path on the backend.

## Decision Drivers

- **Asymmetric preferred** — the backend should verify tokens without holding the signing secret. Avoids the "if my API server is compromised, the attacker can mint tokens" class of breaches.
- **Public-key discovery** — backend should fetch the public key dynamically from a JWKS (JSON Web Key Set) endpoint, so Supabase can rotate keys without coordinated downtime.
- **Compact tokens** — ECDSA signatures are shorter than RSA signatures at equivalent security levels, reducing header overhead on every request.
- **Matches Supabase default** — any deviation would mean configuring Supabase differently, which complicates migration paths.

## Considered Options

1. **ES256 with JWKS auto-discovery** — verify against Supabase's published public key.
2. **HS256 with shared secret** — faster but requires the symmetric secret on the backend.
3. **RS256 with JWKS** — asymmetric, similar model to ES256, but larger signatures.
4. **Accept-all-of-the-above** — detect the algorithm from the token header and pick the verifier accordingly.

## Decision Outcome

**Chosen: ES256 exclusively, with JWKS-based public-key discovery.**

### Rationale

- Supabase's current default. Matching the issuer's default means we don't fight the platform, and it keeps the door open for Supabase to rotate keys without us re-deploying.
- **Asymmetric** — the backend holds only the public key. Even if an attacker extracts everything from the Fly.io machine, they cannot mint new tokens.
- **JWKS endpoint polled on first request** and cached — no static config; key rotation is transparent. See `src/api/auth.py`.
- **ECDSA (P-256 curve)** signatures are ~72 bytes vs RSA-2048's ~256 bytes. On a bearer-token-every-request API, that compresses the `Authorization` header meaningfully over thousands of requests per session.

### Rejected alternatives

- **HS256 with shared secret** — fast, one-line verification, but the backend then holds the symmetric secret that also mints tokens. That creates an equivalence between token signing and token verification that breaks the zero-trust posture. Also, rotating a shared secret requires coordinated deploys across Supabase and our backend.
- **RS256 with JWKS** — fully workable alternative. Rejected because ES256 matches Supabase's default and ECDSA signatures are shorter. No material security difference between ES256 and RS256 at their intended security levels.
- **Accept all three** — implementing a generic "detect the alg from the header" is a well-known security anti-pattern. It invites the `alg: none` and `alg confusion` attack classes. We pin to ES256 server-side and reject anything else.

## Consequences

**Positive**:
- The backend's auth code is ~30 lines in `src/api/auth.py`: fetch JWKS on first call, cache, verify every token with the cached key.
- Rotation is transparent. Supabase can rotate keys and the backend picks them up on the next cache miss.
- No shared secret ever leaves the Supabase control plane.

**Negative**:
- **First request after a cold start pays the JWKS fetch** — adds ~200–500 ms to the first authenticated request. Cached thereafter.
- **Misconfiguration surface** — if a future Supabase project is created with HS256 (legacy), it won't verify here. Documented as a CLAUDE.md gotcha.
- **Slightly more CPU per verification** than HMAC — but negligible at our request rates.

**Neutral**:
- The JWKS URL is derived from `SUPABASE_URL`. Changing Supabase projects requires changing exactly one environment variable.
- If Supabase ever deprecates ES256 in favour of Ed25519 (EdDSA), we'd write ADR-XXXX superseding this one. The JWKS + asymmetric architecture itself would remain unchanged.
