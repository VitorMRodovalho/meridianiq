<!-- Audit run: 2026-04-22 · Layer 1 (Critical) -->
# Camada 1 — Achados Críticos (P0/P1)

Itens que bloqueiam integridade de dados, produção, ou têm impacto de segurança
direto. Todos foram verificados com evidência citada de código/schema.

---

## AUDIT-001 · P0 · Migrations `012_api_keys.sql` e `017_api_keys.sql` definem schemas divergentes da mesma tabela

**Arquivos:** `supabase/migrations/012_api_keys.sql`, `supabase/migrations/017_api_keys.sql`.

**Evidência (diff condensado):**

- `012_api_keys.sql`: `id UUID PRIMARY KEY DEFAULT uuid_generate_v4()`, colunas
  `key_prefix`, `is_active`, `expires_at`; policy `"Users see own keys"`.
- `017_api_keys.sql`: `id BIGINT GENERATED ALWAYS AS IDENTITY`, coluna `key_id TEXT
  NOT NULL UNIQUE`, coluna `revoked_at` em vez de `is_active`; policy `api_keys_select`.

O código runtime em `src/api/auth.py` usa `key_id`, `name`, `key_hash`, `user_id`,
`created_at` — **compatível apenas com 017**.

**Risco:** em qualquer ambiente onde ambas as migrations tenham rodado em ordem,
o segundo `CREATE TABLE api_keys` vai falhar se o primeiro criou com `IF NOT EXISTS`
e o segundo também (schema inconsistente sem erro); ou falhar com "tabela já existe"
se uma não usa `IF NOT EXISTS`. Em ambientes novos, apenas 017 resulta em uma tabela
compatível com o código — mas 012 ainda roda primeiro e pode vencer. Imprevisibilidade
de deploy.

**Ação:**

1. Confirmar em produção qual schema está em vigor (`\d api_keys` via SQL).
2. Remover ou converter `012_api_keys.sql` em `-- archived — superseded by 017`
   (mantendo o arquivo com corpo vazio para preservar numeração histórica).
3. Adicionar teste de regressão em `tests/test_api_keys.py` que força
   `CREATE`→`INSERT`→`SELECT` usando exatamente as colunas que `src/api/auth.py`
   referencia (`key_id`, `key_hash`, `user_id`, `name`, `created_at`).

---

## AUDIT-002 · P1 · `validate_api_key` faz fallback silencioso para dict in-memory quando a tabela Supabase falha

**Arquivo:** `src/api/auth.py` linhas 240–279.

**Código (trecho):**

```260:279:src/api/auth.py
    sb = _get_supabase_client()
    if sb:
        try:
            res = sb.table("api_keys").select("*").eq("key_hash", key_hash).execute()
            if res.data:
                entry = res.data[0]
                return {
                    "id": entry["user_id"],
                    ...
                }
        except Exception:
            pass  # Fall through to in-memory

    entry = _api_keys.get(key_hash)
    if entry is None:
        return None
```

**Risco:**

- `except Exception: pass` **engole** erros de transporte, auth service role quebrada,
  indisponibilidade temporária — e cai num dict in-memory que em produção está vazio
  (ou pior: reciclado entre processos uvicorn). Se `generate_api_key` escreveu em
  Supabase com sucesso mas `validate_api_key` falha ao ler, o usuário vê "Invalid
  API key" sem telemetria.
- Pior caso: se um desenvolvedor em shell interativo popular `_api_keys` via import,
  essa chave **passa a valer em produção** enquanto o Supabase estiver degradado.

Mesmo padrão aparece em `list_api_keys` (linha 291–310) e `revoke_api_key` (313–347).

**Ação:**

1. Trocar `except Exception: pass` por `except Exception as e: logger.error(...)
   raise HTTPException(503, "Auth service degraded")` — fail-closed em vez de
   fail-open silencioso.
2. Remover o fallback in-memory do caminho de produção: guardar atrás de
   `if settings.ENVIRONMENT != "production":`.
3. Emitir métrica/evento Sentry para distinguir "chave inválida" de "auth degradada".

---

## AUDIT-003 · P1 · Rate-limit não aplicado em routers compute-heavy

**Comando executado:**

```bash
for r in src/api/routers/*.py; do \
  endpoints=$(grep -c '@router\.' "$r"); \
  limits=$(grep -c '@limiter.limit' "$r"); \
  printf "%-20s endpoints=%d limited=%d\n" "$(basename $r .py)" "$endpoints" "$limits"; \
done
```

**Matriz resumida (zero-limit, ≥3 endpoints):**

| Router | Endpoints | `@limiter.limit` | Observação |
|---|---|---|---|
| `risk.py` | 8 | **0** | Monte Carlo QSRA — o **mais caro** engine (N=1.000 PERT-Beta samples × forward/backward CPM) |
| `forensics.py` | 10 | **0** | CPA window analysis — recomputa CPM por janela |
| `analysis.py` | 11 | **0** | Hub genérico (DCMA, CPM, scorecard etc.) |
| `reports.py` | 3 | **0** | Geração de PDF via WeasyPrint (pesado + libpango) |
| `exports.py` | 6 | **0** | XER round-trip writer + Excel (pandas/openpyxl) |
| `programs.py` | 5 | **0** | Aggregated rollup via `kpi_helpers.py` (cached, mas ainda expansivo) |
| `benchmarks.py` | 3 | **0** | Cross-project percentile compare |
| `bi.py` | 3 | **0** | BI connector templates |
| `plugins.py` | 2 | **0** | Plugin discovery — baixo custo, mas público |

**Risco:** qualquer requisição autenticada (ou anônima nos endpoints com `optional_auth`)
pode iniciar um Monte Carlo em loop e exaurir CPU da VM Fly (1 shared CPU, 1 GB RAM por
`fly.toml`). Um único ator hostil (ou bug de cliente retry) derruba o serviço.

**Ação prioritária (ordenada por criticidade):**

1. `risk.py`: `@limiter.limit("3/minute")` em `/monte-carlo` + `/simulate` (Monte Carlo
   é **single-use premium**).
2. `forensics.py`: `@limiter.limit("10/minute")` em `/window-analysis`, `/cpa`.
3. `reports.py`: `@limiter.limit("5/minute")` em `/generate/*`.
4. `exports.py`: `@limiter.limit("10/minute")` em `/xer`, `/excel`.
5. `analysis.py`: `@limiter.limit("30/minute")` generalizado — são leituras, mas cumulativas.

---

## AUDIT-004 · P1 · CORS origins hard-coded — deploy em qualquer outro domínio exige code-change

**Arquivo:** `src/api/app.py` linhas 50–65.

```50:65:src/api/app.py
# CORS — whitelist known origins (not wildcard)
_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:4321",
    "https://meridianiq.vitormr.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=3600,
)
```

**Risco:**

- Projeto declara-se open-source → qualquer contribuidor hospedando um fork em domínio
  próprio precisa editar `app.py`. Fricção de adoção.
- Staging, PR preview (Cloudflare Pages branch-deploy), review app de subcontributor:
  todos quebram CORS silenciosamente (browser bloqueia; backend retorna 200 sem header;
  usuário vê "request failed" opaco).

**Ação:**

```python
_CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:4321,https://meridianiq.vitormr.dev"
).split(",") if o.strip()]
```

Adicionar `ALLOWED_ORIGINS` em `.env.example` e documentar no
`docs/DEPLOY_CHECKLIST.md`.

---

**Escopo encerrado desta camada.** Itens P2/P3 estão nas camadas 2 (arquitetura,
schema, segurança, UX, planejado-vs-implementado).
