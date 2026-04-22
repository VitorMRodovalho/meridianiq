<!-- Audit handoff · generated 2026-04-22 · base commit 4a255ee on main -->
# Audit 2026-04-22 — Handoff para o time dev

Este documento lista **todas as ações que a remediação automática NÃO executou**
porque exigem (a) acesso a credenciais de produção, (b) decisão de produto/time, ou
(c) revisão humana antes de merge. Cada item é rastreado por uma issue do GitHub
com o label `requires-human-decision` e — quando aplicável — `ops`.

**Regra de ouro:** nenhuma destas ações deve ser executada por um único indivíduo
sem registro. O checkbox só é marcado quando **pelo menos dois membros do time
(maintainer + um revisor)** concordarem com a execução e o resultado.

---

## Índice

| # | Ação | Severidade | Owner sugerido | Issue | Prazo alvo |
|---|---|---|---|---|---|
| H-01 | Aplicar migration 026 em produção (Supabase) | **P0** | Maintainer + DBA/ops | [`#26`](https://github.com/VitorMRodovalho/meridianiq/issues/26) | Próxima janela de manutenção (≤ 7 dias) |
| H-02 | Criar `docs/ROADMAP.md` no kickoff do Cycle 2 | **P2** | Product/tech-lead | [`#27`](https://github.com/VitorMRodovalho/meridianiq/issues/27) | Kickoff Cycle 2 |
| H-03 | Revisar/aceitar ADR-0017 e ADR-0018 | **P2** | Todo o time (council review) | [`#28`](https://github.com/VitorMRodovalho/meridianiq/issues/28) | Antes de Cycle 2 |
| H-04 | Revisar + merge dependabot PRs abertos (#11, #15) | **P3** | Maintainer | — (sub-item de #24) | Semanal (ritual) |
| H-05 | Deletar branches locais obsoletas `v0.{2,3,4,5}-*` | **P3** | Maintainer local | — (sub-item de #24) | Ad-hoc |
| H-06 | Bump Dockerfile 3.13 → 3.14 | **P3** | Maintainer | — (sub-item de #24) | Próximo `chore(infra)` |
| H-07 | Fechar gaps de i18n (15 páginas com ≤ 4 chaves `$t()`) | **P2** | Frontend eng | [`#22`](https://github.com/VitorMRodovalho/meridianiq/issues/22) | 3-5 sprints |
| H-08 | Abrir sub-issues para Wave 7 (resource + cost Gantt) | **P2** | Product + frontend | [`#23`](https://github.com/VitorMRodovalho/meridianiq/issues/23) | Re-escopar no Cycle 2 |

---

## H-01 · Aplicar migration 026 em produção

**Por que existe:** ADR-0017 e a dedup `012`↔`017` foram shipadas em código
(commit `cd3b907`), mas a migration 026 **ainda não rodou no banco de produção**.
Enquanto não rodar, instâncias Supabase em que 012 foi aplicada antes de 017
permanecem com `api_keys (id UUID, key_prefix, is_active, expires_at)` —
esquema incompatível com `src/api/auth.py`. Qualquer tentativa de criar/validar
API key hoje **falha silenciosamente** (insert rejeita por coluna ausente, ou
a fail-closed do commit `06fa945` retorna 503).

**Quem executa:** maintainer **ou** DBA/ops com acesso ao Supabase console.

**Quem revisa:** um segundo membro do time (code-review da issue + confirmação
visual do output dos diagnósticos).

**Checklist de execução:**

1. **Diagnóstico (read-only, qualquer hora):**

   ```sql
   -- Via Supabase SQL editor, conectado ao schema `public`
   \d api_keys
   SELECT column_name, data_type, is_nullable
     FROM information_schema.columns
    WHERE table_name = 'api_keys'
    ORDER BY ordinal_position;

   SELECT name, executed_at
     FROM supabase_migrations.schema_migrations
    WHERE name LIKE '%api_keys%'
    ORDER BY executed_at;
   ```

   Colar o output na issue #26.

2. **Decidir o caminho:**
   - **Schema já é o de 017** (colunas `key_id`, `revoked_at` presentes; sem
     `key_prefix`, `is_active`, `expires_at`) → rodar 026 é **no-op seguro**.
   - **Schema é o de 012** (presença de `key_prefix` ou `is_active`) → 026 faz
     o trabalho real: backfill `key_id`, translate `is_active=FALSE →
     revoked_at`, drop colunas legadas.

3. **Backup antes do apply (obrigatório):**

   ```sql
   CREATE TABLE api_keys_backup_20260422 AS SELECT * FROM api_keys;
   SELECT COUNT(*) FROM api_keys_backup_20260422;
   ```

4. **Aplicar 026:**

   ```bash
   # Via supabase CLI, apontando para o projeto prod:
   supabase link --project-ref <PROJECT_REF>
   supabase db push supabase/migrations/026_api_keys_schema_align.sql
   ```

   Alternativa sem CLI: copiar o conteúdo de
   `supabase/migrations/026_api_keys_schema_align.sql` e executar no SQL editor.

5. **Verificação pós-apply:**

   ```sql
   \d api_keys
   -- Esperado: id (bigint), key_id (text unique), key_hash (text unique),
   --          user_id (uuid), name (text), created_at, revoked_at, last_used_at.
   SELECT count(*) FROM api_keys;                -- igual ao backup
   SELECT count(*) FROM api_keys WHERE key_id LIKE 'legacy_%';  -- rows backfilladas
   ```

6. **Smoke test runtime:**
   - Em staging / ou com dry-run: criar uma API key via `POST /api/v1/api-keys`,
     validá-la via `X-API-Key` header em `GET /api/v1/health` com auth opcional,
     revogá-la via `DELETE /api/v1/api-keys/{key_id}`.
   - Confirmar código `200`/`401` corretos.

7. **Registro:** comentar o resultado na issue #26 com:
   - output dos diagnósticos dos passos 1 e 5;
   - número de rows backfilladas;
   - horário do apply;
   - quem executou e quem revisou.

**Rollback:** o backup em `api_keys_backup_20260422` permite restaurar via
`DROP TABLE api_keys; ALTER TABLE api_keys_backup_20260422 RENAME TO api_keys;`
(re-aplicar RLS + policies manualmente após o rename). Preservar o backup por
≥ 30 dias antes de descartar.

---

## H-02 · Criar `docs/ROADMAP.md` no kickoff do Cycle 2

**Por que existe:** ADR-0018 formalizou que cada cycle-close deve atualizar 5
artefatos (ROADMAP, BUGS pruning, LESSONS_LEARNED, catalog regen, audit re-run).
O único que **ainda não existe** é `docs/ROADMAP.md` — hoje o roadmap vive
fragmentado em ADR-0009 (cycle-specific, denso) e `docs/SCHEDULE_VIEWER_ROADMAP.md`
(feature-specific, desatualizado).

**Quem executa:** Product / tech-lead. Rascunho idealmente em PR para review do time.

**Checklist:**

- [ ] Decidir em time o escopo do Cycle 2 (tema-umbrella + waves estimadas).
- [ ] Listar itens deferidos de Cycle 1 que entram no Cycle 2 (ex: #8, #14,
      parte de #22 e #23).
- [ ] Listar pesquisa/research items (federated learning, BIM-lite, GIS)
      num "não agendado" para não poluir o plano.
- [ ] Abrir PR com `docs/ROADMAP.md` seguindo esboço abaixo.
- [ ] Dois reviewers aprovam antes do merge.

**Esboço sugerido (preencher em time):**

```markdown
# MeridianIQ — Roadmap

## Cycle atual: 2 (kickoff YYYY-MM-DD, target close YYYY-MM-DD)
Theme: <"Resource & Cost Integration" ou outro>

### Committed scope
- Wave 1: …
- Wave 2: …

### Stretch (se wave 2 fechar cedo)
- …

## Cycle 3 (tentativo)
…

## Deferred
- Lifecycle health engine — ADR-0010 reservado (ver ADR-0009 §W4 outcome)
- Fuzzy-match dep category — ADR-0011 reservado
- Federated learning, BIM-lite, GIS linear scheduling — research-only

## Não planejado
Issues marcadas `research` / `won't fix this cycle` aparecem aqui quando
explicitamente desescopadas.
```

---

## H-03 · Revisar/aceitar ADR-0017 e ADR-0018

**Por que existe:** Os dois ADRs foram marcados como `accepted` pelo agente de
remediação. A convenção do projeto (ADR-0000) é que aceitação pressupõe
revisão humana — portanto tecnicamente devem passar por um ciclo `proposed →
accepted` com aprovação do time.

**Opções:**

1. **Ratificar como-está** — se o time lê e concorda, manter status `accepted`,
   comentar na issue #28 "ratificado por <nomes> em <data>" e fechar a issue.
2. **Reabrir como `proposed`** — se alguém tem objeção estrutural, editar o
   header do ADR para `status: proposed`, discutir em PR ou issue, re-aceitar
   após consenso.
3. **Superseder** — se a discussão levar a uma decisão diferente, autorar um
   novo ADR que supersede 0017 ou 0018, sem editar os originais (ADR-0000 exige
   imutabilidade histórica).

**Itens cegos que merecem discussão explícita:**

- ADR-0017 escolheu opção 3 (012 no-op + 026 align) vs opções 1 (deletar 012)
  e 2 (reescrever 012). Se o time preferir outra, documentar.
- ADR-0018 afirma que o cycle-close deve atualizar 5 artefatos **socialmente**
  (sem pre-commit hook). Se o time quiser enforçar via CI, autorar um ADR
  complementar.

---

## H-04 · Revisar + merge dependabot PRs abertos

Sub-item de #24. PRs abertos no momento desta auditoria:

- [#11](https://github.com/VitorMRodovalho/meridianiq/pull/11) —
  `actions/upload-artifact` v6 → v7 · CI verde · baixo risco.
- [#15](https://github.com/VitorMRodovalho/meridianiq/pull/15) — frontend
  minor-patch group · CI verde · baixo risco.

**Ritual sugerido:** agendar 15 min semanais (ex: toda segunda-feira) para o
maintainer revisar dependabot. Não precisa abrir issue separada — ritmo
operacional.

---

## H-05 · Deletar branches locais obsoletas

Sub-item de #24. Só afeta o clone local do maintainer (branches nunca foram
empurradas para `origin`). Comando:

```bash
git branch -D v0.2-forensics v0.3-claims v0.4-controls v0.5-risk
```

Verificação de segurança antes de deletar — confirmar que são subsets das tags:

```bash
for b in v0.2-forensics v0.3-claims v0.4-controls v0.5-risk; do
  echo "=== $b ==="
  tag="${b%-*}.0"
  git log "$b" ^"$tag" --oneline | head -5 && echo "(subset empty = safe to delete)"
done
```

---

## H-06 · Bump Dockerfile Python 3.13 → 3.14

Sub-item de #24. A justificativa "pyiceberg não tem wheel 3.14" não se aplica
(dep não está em `pyproject.toml`). CI já roda em 3.14 — alinhar o deploy
reduz drift.

Plano:

1. Editar `Dockerfile`: `FROM python:3.13-slim` → `FROM python:3.14-slim`.
2. `docker build .` local para confirmar que todas as wheels instalam.
3. Subir PR com title `chore(infra): Dockerfile Python 3.13 → 3.14`.

---

## H-07 · Fechar gaps de i18n

Issue [#22](https://github.com/VitorMRodovalho/meridianiq/issues/22). 15
páginas com ≤ 4 chamadas a `$t()`. Trabalho por sprint, não por wave — 3
páginas por sprint ao longo de ~5 sprints fecham.

Priorização sugerida (por tráfego / centralidade):

1. `schedule`, `risk`, `whatif`, `optimizer` — core flows.
2. `cashflow`, `anomalies`, `root-cause`, `reports` — cross-referenced.
3. Os demais.

---

## H-08 · Sub-issues para Wave 7 (resource + cost Gantt)

Issue [#23](https://github.com/VitorMRodovalho/meridianiq/issues/23) é hoje
um umbrella. Quando Cycle 2 arrancar (ou ao final da fase de roadmap H-02),
abrir sub-issues:

- Resource histogram below Gantt
- Cost-loading curve overlay on timeline
- Budget vs actual per activity (precisa CBS persistence)
- Resource-constrained CP highlighting

---

## Como registrar conclusão

Para cada item acima, ao fechar a issue:

1. Comentar na issue o **output da verificação** (ex: diff de schema, print
   do console, link para commit/PR).
2. Comentar o **quem fez / quem revisou** com data.
3. Atualizar o checkbox correspondente aqui em `HANDOFF.md` via PR e mergear.
4. Atualizar o meta-issue [#25](https://github.com/VitorMRodovalho/meridianiq/issues/25)
   cruzando o item como concluído.

Quando todos os items H-01..H-06 estiverem fechados, comentar em #25 "handoff
encerrado" e remover o label `requires-human-decision` da issue.

---

## Contato

- Mantenedor: @VitorMRodovalho
- Canal de segurança: vitorodovalho@gmail.com · `[MeridianIQ security] …`
- Para dúvidas sobre esta auditoria: comentar na issue relevante **ou** no
  meta-issue [#25](https://github.com/VitorMRodovalho/meridianiq/issues/25).
