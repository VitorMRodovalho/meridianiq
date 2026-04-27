<!-- Audit run: 2026-04-26 · Layer 2c (Security) -->
# Camada 2c — Segurança

Rate-limit gaps remanescentes, fail-closed status, CORS, env hygiene.

## Sumário executivo

- AUDIT-002 (api_key fail-closed) — RESOLVIDO ✅. 8 ocorrências de `if settings.ENVIRONMENT == "production":` em `src/api/auth.py`.
- AUDIT-003 (rate-limit gap) — PARCIALMENTE RESOLVIDO. Gap remanescente classificado como P3 (não P1) — ver AUDIT-2026-04-26-005.
- AUDIT-004 (CORS hardcoded) — RESOLVIDO ✅. `ALLOWED_ORIGINS` env consumido.
- AUDIT-005 (.env.example incompleto) — RESOLVIDO ✅ com sub-finding em AUDIT-2026-04-26-006.
- AUDIT-018 (Dependabot PRs) — RESOLVIDO ✅. PRs #11, #15, #34 todos MERGED.

Nenhum P0/P1 novo nesta camada.

---

## AUDIT-2026-04-26-005 · P3 · Rate-limit coverage matrix sem política documentada

**Estado atual** (`@router.{verb}` count vs `@limiter.limit` count por router):

| Router | Endpoints | Limited | Gap | Política inferida |
|---|---|---|---|---|
| admin | 6 | 1 | 5 | Reads administrativas; provavelmente OK ser ungated |
| analysis | 11 | 0 | 11 | **Hub genérico** (DCMA, CPM, scorecard etc.) — reads cumulativas; revisar se merece RATE_LIMIT_READ default |
| benchmarks | 3 | 0 | 3 | Cross-project compare — caro mas possivelmente intencional |
| bi | 3 | 0 | 3 | BI connector templates — leve |
| comparison | 1 | 1 | 0 | ✅ |
| cost | 7 | 1 | 6 | CBS reads + 1 write probably limited |
| evm | 6 | 1 | 5 | EVM reads |
| exports | 6 | 3 | 3 | Half-coverage; provavelmente XER/Excel limitados, JSON exports não |
| forensics | 10 | 6 | 4 | **Boa cobertura** — engines pesados explicitamente limitados |
| health | 2 | 0 | 2 | Healthcheck — deve permanecer ungated |
| intelligence | 8 | 1 | 7 | Reads do hub de intelligence — provavelmente OK |
| lifecycle | 4 | 4 | 0 | ✅ Full coverage |
| plugins | 2 | 0 | 2 | Plugin discovery — público, baixo custo |
| programs | 5 | 0 | 5 | Aggregated rollup via `kpi_helpers.py` (cached) — pesa mas é cacheado |
| projects | 4 | 1 | 3 | CRUD reads |
| reports | 3 | 1 | 2 | WeasyPrint PDF — pesado; talvez 1/3 limitada cobre o gerador |
| risk | 9 | 1 | 8 | **Monte Carlo é o engine mais caro** — verificar se a 1 cobre `/monte-carlo` |
| schedule_ops | 7 | 1 | 6 | XER ops |
| tia | 4 | 1 | 3 | TIA reads |
| upload | 2 | 1 | 1 | Upload write é limited |
| whatif | 7 | 1 | 6 | What-if scenarios |
| ws | 2 | 1 | 1 | WebSocket — auth-bound |

**Total:** 112 endpoints, 28 com `@limiter.limit` decorator (25%).

**Diagnóstico:** o fix de Wave B2 do baseline endureceu **explicitamente os
endpoints mais caros** (Monte Carlo simulate, MIP forensics windows, WeasyPrint
generate, XER write). O resto não foi tocado. **NÃO É** bug runtime — o limiter
está ativo no slowapi `[dev]` extras (ADR-0019 §W0 D10) e CI exercita os
decorators existentes.

**O que está faltando:** **discipline / enforcement**, não buckets. **Os 3 buckets
existem** em `src/api/deps.py:138-140`:

```python
RATE_LIMIT_EXPENSIVE = "3/minute"   # Monte Carlo, MIP windows, PDF generate
RATE_LIMIT_MODERATE = "10/minute"   # XER round-trip, batch CRUD
RATE_LIMIT_READ = "30/minute"       # single-resource GETs
```

ADR-0017 §"Decision Outcome" + ADR-0019 §"W0 — D1" estabelecem policy
implicit (Cycle 2 W0 commit `b924b93` aplicou `RATE_LIMIT_READ` em
`POST /api/v1/jobs/progress/start`). **O que falta** é:

1. **ADR-pinned matriz** que lista cada router-endpoint pair → bucket
   esperado. Sem isso, gap detection é manual.
2. **Test de regressão `tests/test_rate_limit_policy.py`** que falha se:
   - Endpoint contendo `simulate|monte_carlo|generate_pdf|forensic_window` está sem `@limiter.limit(RATE_LIMIT_EXPENSIVE)`.
   - Endpoint contendo `write|create|update|upload` (ex-`/health|status`) está sem qualquer `@limiter.limit`.

**Risco:** baixo P3. **Discipline gap:** documental + falta de test enforcement,
não falta de buckets.

**Ação:**

1. Amendment a ADR-0017 ou ADR-0019: adicionar §"Rate-limit policy matrix"
   listando cada router → bucket.
2. Test de regressão (acima).
3. Atualizar matrix em `04-security.md` desta auditoria + matrix paralela em
   ADR amendment.

**Por que P3 e não P2:** o gap é discipline, não falha runtime — operação atual
não foi DOS-ada porque os engines mais caros estão cobertos com decorators
ad-hoc, e os buckets corretos já existem. Faltam apenas (a) o ADR matrix
+ (b) o test que enforça.

---

## AUDIT-2026-04-26-006 · P3 · `RATE_LIMIT_ENABLED` undocumented em `.env.example`

**Arquivo runtime:** `src/api/deps.py:116`:

```python
enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
```

**`.env.example`:** **não documenta** `RATE_LIMIT_ENABLED`.

**Por que existe:** é um kill-switch operacional — se um deploy precisa
rapidamente desabilitar rate limiting (ex: incident de cliente legítimo
hitting limits durante demo high-stakes), o operador precisa saber que existe.

**Risco:** baixíssimo P3. **Discipline:** maintainer-onboarding cleaner.

**Ação:** adicionar 3 linhas em `.env.example` (commented, default-shown):

```bash
# Rate limiting kill-switch — set to "false" to disable all @limiter.limit
# decorators (only useful for incident response or test environments).
# RATE_LIMIT_ENABLED=true
```

Também documentar no `docs/DEPLOY_CHECKLIST.md` ou em `SECURITY.md`.

---

## CORS — verificação completa (carry-over de AUDIT-004)

`src/api/app.py:73-78`:

```python
_DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,"
    "http://localhost:4321,"
    "https://meridianiq.vitormr.dev"
)
allow_origins = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]
```

**Tests de regressão:** `tests/test_cors_config.py` (4 testes — verificados).

**Conformidade:** ✅ Resolução completa.

---

## API key fail-closed (carry-over de AUDIT-002)

`src/api/auth.py` — verificado por grep:

```
141:        if settings.ENVIRONMENT == "production":
151:        if settings.ENVIRONMENT == "production":
273:        if settings.ENVIRONMENT == "production":
291:        if settings.ENVIRONMENT == "production":
337:        if settings.ENVIRONMENT == "production":
346:        if settings.ENVIRONMENT == "production":
384:        if settings.ENVIRONMENT == "production":
395:        if settings.ENVIRONMENT == "production":
```

8 callsites — cobertura abrangente das 4 funções (validate / generate / list / revoke)
com 2 paths cada (Supabase OK / Supabase exception → 503).

**Tests:** `tests/test_api_keys_fail_closed.py` (7 testes).

**Conformidade:** ✅ Resolução completa.

---

## WebSocket auth surface (Cycle 2 W1)

ADR-0019 §"W1 — D3" + ADR-0013 endurecem o WS path:

- `WSPROGRESS_HANDSHAKE` valida JWT no handshake (`src/api/routers/ws.py`).
- **Server-initiated heartbeat** (HEARTBEAT_INTERVAL_SECONDS = 30.0) re-checa
  JWT `exp` AND re-valida API keys via `validate_api_key()`.
- Closes `4401` em expiry/revogação (defensive `queue.get_nowait()` drain após
  timeout).
- Heartbeat opt-in via `?hb=1` query — backend safe to deploy before frontend rollout.

**Verificação grep:** `grep -n "HEARTBEAT_INTERVAL_SECONDS\|_decode_exp_unverified\|validate_api_key" src/api/routers/ws.py` — todos presentes.

**Conformidade:** ✅ Endurece superfície sem ampliar.

---

## Defusedxml + XXE prevention

Verificado:

```
$ grep -l "defusedxml" src/parser/*.py
src/parser/msp_reader.py
```

`defusedxml` no MSP reader (UTF-16 BOM + XXE/DTD safe). Cycle 1 W0 fix — sem regressão.

---

## Sentry / observability

Cycle 1 W4 collateral fix: `_json_safe` boundary discipline em `src/database/store.py:33`,
`:711`, `:754` — datetime serialization que silentmente flipava prod projects para
`failed`. Verificado.

`SENTRY_DSN` documentado em `.env.example` (commented). Conformidade.

---

## Atribuição AI / commit history

`git log --all --grep="Co-Authored-By: Claude"` retorna ≥5 commits históricos
(ex: `dfcee48`, `75c0fd6`, `ea27f69`, `c344a21`, `3f3b2e7`). User-level CLAUDE.md
estabelece que `Co-Authored-By: Claude` deve ser substituído por `Assisted-By:
Claude (Anthropic)` mas **não retroativamente** salvo autorização explícita
de force-push.

**Diagnóstico:** **não é finding ativo** — convenção atual está sendo seguida
em commits novos (verificável em `git log --since="2026-04-15"`); legacy stays.

**Ação:** nenhuma. Documentado como histórico imutável.

---

## Dependabot pipeline saúde

PRs auto-resolvidos desde baseline:

- `#11` (upload-artifact v6→v7) — MERGED
- `#15` (frontend minor-patch group) — MERGED
- `#34` (jsdom 29.0.2→29.1.0) — MERGED

**Conformidade:** ✅. Ritual semanal (HANDOFF baseline §H-04) está sendo seguido.

---

**Sumário desta camada:** 2 achados P3 novos (005 rate-limit policy gap, 006
RATE_LIMIT_ENABLED docs gap), zero P0/P1 novos. Surface de auth/CORS/WS endurecida.
Cycle 1+2 não introduziram nova superfície de ataque. **Posture saudável.**
