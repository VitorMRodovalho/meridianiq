<!-- Audit run: 2026-04-22 · Layer 2c -->
# Camada 2c — Segurança

Referências cruzadas: P1s já detalhados em [Camada 1](01-critical-findings.md).

## Sumário

| Área | Estado |
|---|---|
| Hardcoded secrets | ✅ Ausentes (gitleaks CI ativo) |
| XXE / billion-laughs | ✅ Mitigado (`defusedxml.ElementTree.fromstring` + `forbid_dtd=True` em `src/parser/msp_reader.py`) |
| Stored XSS | ✅ Svelte auto-escape; nenhum `{@html}` em `web/src/routes/` |
| SQL injection | ✅ Supabase client parametrizado; nenhum SQL textual em código Python |
| CORS wildcard em 5xx | ✅ Removido (v2.x); middleware atual usa whitelist |
| Security headers | ✅ HSTS + X-Frame + Referrer-Policy + X-CTO + Permissions-Policy em `app.py:69–79` |
| RLS por tabela user-owned | ✅ Coberto (ver Camada 2b) |
| JWT verification | ✅ JWKS para ES256 (ADR-0005), com fallback HS256 retrocompat |
| Rate-limit | ⚠ **Parcial** — ver AUDIT-003 |
| API key fallback | ⚠ **Silencioso** — ver AUDIT-002 |
| CORS configuração por ambiente | ⚠ **Hardcoded** — ver AUDIT-004 |
| `.env.example` completude | ⚠ **Incompleto** — ver AUDIT-005 abaixo |

---

## AUDIT-005 · P2 · `.env.example` incompleto

**Arquivo:** `.env.example` (10 linhas).

**Atualmente contém:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`ENVIRONMENT`.

**Precisa incluir** (todas referenciadas em código mas ausentes do exemplo):

| Variável | Uso | Arquivo |
|---|---|---|
| `SUPABASE_JWT_SECRET` | Verificação HS256 (retrocompat) | `src/api/auth.py:67` |
| `ALLOWED_ORIGINS` | Override CORS (após AUDIT-004) | `src/api/app.py:51` |
| `SENTRY_DSN` | Telemetria production | `src/api/app.py:17` |
| `ANTHROPIC_API_KEY` | NLP Query + Conversational Builder | `src/analytics/nlp_query.py` |
| `FLY_API_TOKEN` | Deploy via `fly deploy` (CI/CD only) | `CLAUDE.md:80` |
| `POSTHOG_KEY` / `PUBLIC_POSTHOG_KEY` | Analytics web (`posthog-js` em deps) | `web/package.json:40` |
| `PORT` | Uvicorn port override (Fly.io define 8080) | `fly.toml:9` |

**Ação:** atualizar `.env.example` com comentários explicando qual variável é
obrigatória em dev, em prod, e qual é opcional.

---

## AUDIT-003 · P1 · Rate-limit parcial (detalhe)

Matriz exata (contagem `@limiter.limit` por router):

```
admin             1 de  6 endpoints     (17%)
analysis          0 de 11 endpoints     ⚠
benchmarks        0 de  3 endpoints     ⚠
bi                0 de  3 endpoints     ⚠
comparison        1 de  1 endpoints    (100%)
cost              1 de  7 endpoints
evm               1 de  6 endpoints
exports           0 de  6 endpoints     ⚠
forensics         0 de 10 endpoints     ⚠
health            0 de  2 endpoints  (OK — healthz público)
intelligence      1 de  8 endpoints
lifecycle         4 de  4 endpoints    (100%)
plugins           0 de  2 endpoints
programs          0 de  5 endpoints     ⚠
projects          1 de  4 endpoints
reports           0 de  3 endpoints     ⚠ (PDF = pesado)
risk              0 de  8 endpoints     ⚠⚠ (Monte Carlo)
schedule_ops      1 de  7 endpoints
tia               1 de  4 endpoints
upload            1 de  2 endpoints
whatif            1 de  7 endpoints
ws                0 de  2 endpoints  (N/A — WS usa guard próprio)
```

**Prioridade-1 (aplicar esta semana):** `risk.py`, `forensics.py`, `reports.py`,
`exports.py`. Estes endpoints são os **caros** — Monte Carlo, window analysis por
época, PDF WeasyPrint, XER round-trip.

**Prioridade-2:** `analysis.py` (11 endpoints), `programs.py`, `benchmarks.py`,
`bi.py`, `plugins.py`. Baratos por unidade mas abusáveis em volume.

Sugestão de constantes compartilhadas em `src/api/deps.py`:

```python
RATE_LIMIT_EXPENSIVE = "3/minute"    # Monte Carlo, PDF, XER export
RATE_LIMIT_MODERATE  = "10/minute"   # Window analysis, comparison
RATE_LIMIT_READ      = "30/minute"   # Cached reads, aggregated rollups
```

Facilita auditoria futura e consistência entre routers.

---

## Auth flow — observações

### `src/api/auth.py:77`

```python
elif alg in ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512"):
```

O docstring do módulo diz "supports HS256, RS256, ES256" mas o código aceita ES384,
ES512, RS384, RS512 via JWKS. ADR-0005 fixa **ES256** como decisão. Não é bug —
JWKS negocia o alg dinamicamente — mas vale alinhar docstring + ADR para clareza.

### Production fail-open

`optional_auth` em `src/api/auth.py:122–153` tem o padrão correto:

```python
if not credentials:
    if settings.ENVIRONMENT == "production":
        raise HTTPException(401, ...)
    return None
```

Porém, em `get_current_user` (linha 46), se `SUPABASE_JWT_SECRET` não estiver setado
em prod (deploy mal configurado), a função retorna `None` **silenciosamente** (`return
None` na linha 70). Um endpoint protegido via `optional_auth` com HS256 token + env
quebrado vai aceitar como "sem auth". **P2 hardening:** em `ENVIRONMENT=production`,
`SUPABASE_JWT_SECRET` ausente + token HS256 presente deveria ser 503, não 200.

---

## LGPD/GDPR

**Presente:**

- `supabase/migrations/014_security_rpcs.sql` — RPC `delete_user_data(target_user_id)`
  encadeia DELETE em todas as tabelas user-owned.
- `src/api/routers/admin.py:95` — endpoint `DELETE /api/v1/admin/user-data` chama
  a RPC via `store._client.rpc(...)`.
- `PRIVACY.md` (12 KB) documenta bases legais e retenção.

**Gaps (hypothesis-level — precisa revisão jurídica binding):**

- Não há UI em `web/src/routes/settings/` que expõe "Delete my data" botão.
  Usuário precisa chamar API ou contatar mantenedor. P2 UX gap.
- Nenhum workflow de **export de dados** (LGPD art. 18 "portabilidade";
  GDPR art. 20). P3 — só relevante se atrair usuários regulados.
- `audit_trail_user_agent` (migration 021) capta `user_agent` e IP (via `_client_ip()`
  honrando XFF). Verificar se retenção está documentada. Se for indefinida, é
  violação técnica de minimização.

---

## Dependabot aberto

- **PR #11** `chore(ci): bump actions/upload-artifact from 6 to 7` — CI verde.
  Revisar + merge. Baixo risco.
- **PR #15** `chore(deps)(deps): bump the frontend-minor-patch group across 1
  directory with 4 updates` — CI verde. Revisar + merge.

**Ação (P3 mas baixo esforço):** limpar a fila semanalmente evita que patches de
security demorem a chegar.

---

## Governança aplicada — manter

- `gitleaks.yml` workflow em todo push + PR.
- CodeQL scheduled.
- `SECURITY.md` define canal PVR (private vulnerability reporting).
- `.gitleaks.toml` com regras customizadas para o repo (boa prática).
- `CONTRIBUTING.md` + `CODE_OF_CONDUCT.md` + `GOVERNANCE.md` completos.
