# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-011
**План:** [plan/T-HUB-011-analyze-pre-implement/md/plan.md](../plan/T-HUB-011-analyze-pre-implement/md/plan.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-23
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (BACK: один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../.cursor/templates/decompose/epic-step.yaml).

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.** `index.md` status — best-effort зеркало (`mark-index-status` / `finalize-step` / auto `repair-index-mirror` на prepare).
> **`index.yaml` contract:** `schema: epic-decompose-index/v1`, корневой список `steps:`, у шага минимум `id`, `file`, `title`, `next_phase`, `status`. `queue:` / `step_id:` в корне индекса недопустимы.
> `--decompose` = `index.md` | `index.yaml` | каталог | shard yaml рядом. Не передавать implement-шард.
> PLAN / другой чат **не** пишет весь этот файл и **не** трогает status, пока эпик в IMPLEMENT/loop.
> Рассинхрон → `repair-index-mirror` (rebuild queue из yaml). Состав yaml из md → `sync-index-yaml` (bootstrap).
> Plan не дублирует чеклист шагов. `implement/index.md` не создавать.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `query-builder` | INTEG: list/filter endpoints (не используется в этом эпике) |

**Per-step:** BACK — skills gate в каждом `sNN` (`workflow-decompose.mdc`). INTEG — lean §Contract в `eNN`, без gap/contracts as input.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.  
> Канон: `workflow-*-decompose.mdc` §Maximal detail.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-1 | `workflow-analyze.mdc` × BACK (+ FRONT/INTEG) + `_lean/analyze.mdc` | s01, s02 | BACK в s01; FRONT/INTEG в s02 |
| FR-2 | Команды в `mainrule.mdc` + role indexes + slash `{back,front,integ}-analyze.md` | s02 | mainrule + slash |
| FR-3 | Шаблон `.cursor/templates/analyze/epic-analyze.yaml` schema `epic-analyze/v1` | s01 | schema в s01 |
| FR-4 | Detection passes (Duplication, Ambiguity, Underspecification, Coverage Gaps, Inconsistency, Constitution) | s01 | core detection text в s01 |
| FR-5 | Output: findings table + coverage summary + metrics (coverage %, critical count) | s01 | schema + workflow output contract |
| FR-6 | Next Actions: CRITICAL → fix plan/decompose / CLARIFY; else may IMPLEMENT | s03 | wired в finish-doc-router + implement |
| FR-7 | `finish-doc-router`: ANALYZE → load_now analyze artifact; next IMPLEMENT или DECOMPOSE/CLARIFY | s03 | finish-doc-router edit |
| FR-8 | `workflow-*-decompose.mdc` FINISH: рекомендовать `* ANALYZE` перед IMPLEMENT | s03 | DECOMPOSE workflow edit |
| FR-9 | `workflow-*-implement.mdc`: если в `load_now` свежий analyze с `critical>0` — WARN/FAIL soft | s03 | IMPLEMENT workflow edit |
| FR-10 | memory-bank-paths: analyze/ | s03 | paths edit |
| FR-11 | refs: `memory-bank/back/plan/refs/speckit-adapt-011.md` | s04 | refs doc |
| FR-12 | Parity role-command / agents mirror | s04 | role-command SKILL edit |
| AC+ #1 | Команды ANALYZE в mainrule + существуют workflow/lean/template/slash | s01, s02 | coverage |
| AC+ #2 | Schema yaml содержит: `findings[]`, `coverage[]`, `metrics`, `critical_count`, `recommendation` | s01 | schema |
| AC+ #3 | DECOMPOSE workflow упоминает ANALYZE | s03 | decompose edit |
| AC+ #4 | Dry-run: фиктивный epic с FR без sNN → finding Coverage CRITICAL/HIGH | s04 | fixture + docs |
| AC+ #5 | `rg` на `STRICTLY READ-ONLY` / запрет правок кода в workflow-analyze | s01, s02 | gates |
| AC+ #6 | refs-doc: что взяли из analyze.md / что нет (hooks, scripts) | s04 | refs |
| NFR-1 | Token-efficient: progressive disclosure входов; не dump всего plan | s01 | lean load в workflow/gates |
| NFR-2 | Deterministic IDs findings (`A1` category prefix) при повторном прогоне без изменений | s01 | detection passes |
| NFR-3 | Не запускать pytest/vitest в ANALYZE | s01, s02 | gates + workflow |
| NFR-4 | Не модифицировать decompose/implement/code | s01, s02 | STRICTLY READ-ONLY |
| NFR-5 | Do Not Touch: AUDIT schema (012), clarify UX (010), loop.sh gates | s01 | explicit boundary |
| AC− #1 | Не создавать `sNN-audit-*` из ANALYZE (это AUDIT) | s01 | boundary documented |
| AC− #2 | Не требовать FEATURE_DIR/specs | s01 | workflow: plan/decompose artifacts |
| AC− #3 | Не hard-block `loop.sh` без отдельного эпика | s01 | soft WARN, не gate |
| AC− #4 | Не читать полный текст всех implement yaml (их ещё нет) | s01 | lean load: headers only |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Schema template + BACK workflow/lean + core detection | plan §До DECOMPOSE s01 | s01 |
| FRONT/INTEG + slash + mainrule | plan §До DECOMPOSE s02 | s02 |
| Wire DECOMPOSE/IMPLEMENT/finish-doc-router/paths | plan §До DECOMPOSE s03 | s03 |
| refs + dry-run fixture/docs + role-command parity | plan §До DECOMPOSE s04 | s04 |

## Outcome map (plan → steps)

> **HARD (BACK):** не ужимать Goal/NFR плана до infra-slug. Канон: `workflow-*-decompose.mdc` §Outcome preserve.  
> **Map ≠ замена шагов:** каждый критичный outcome должен иметь **sNN в очереди** с outcome-first `title`, не только строку здесь.  
> Черновик числа шагов в plan — **advisory**; добавляй sNN пока coverage без дыр.  
> Строки: проблема/outcome → sNN. Краткий out_of_scope / follow-up — сюда же.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Перед кодом есть детерминированный отчёт: coverage %, contradictions, ambiguity leftovers, unmapped steps — с Next Actions | s01, s02, s03, s04 |
| CRITICAL → не стартовать IMPLEMENT без fix/defer (severity heuristic, coverage table) | s01, s03 |
| ANALYZE ≠ AUDIT: read-only до кода, не создаёт audit-shards | s01 (boundary documented) |
| 50-cap findings + overflow summary (как Spec Kit) | s01 (schema + workflow) |
| Constitution (если есть) → MUST violations = CRITICAL | s01 (detection pass) |
| DECOMPOSE FINISH tip: `* ANALYZE` рекомендуется (soft, не hard-block loop) | s03 |
| IMPLEMENT: если critical>0 и user не override — WARN/FAIL soft (Handoff note) | s03 |
| Dry-run fixture: фиктивный epic с FR без sNN → finding Coverage CRITICAL | s04 |
| Parity: BACK/FRONT/INTEG + role-command + agents mirror | s02, s04 |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** roadmap `.queue.yaml`).  
> Add без delete-шага в очереди = FAIL. Любая строка ≠ n/a → финальный `*-legacy-fallback-purge` в очереди. Greenfield → одна строка `n/a — нет замен`.  
> `Kind`: A=code · B=entrypoint/deploy · C=fallback. `Fallback?=yes` → deletes in-epic (не откладывать).  
> Канон: `workflow-*-decompose.mdc` §Replacement cleanup · @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| n/a — нет замен | — | — | — | — | greenfield (новый режим ANALYZE) |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-analyze-schema-back-workflow-lean-detection.yaml](s01-analyze-schema-back-workflow-lean-detection.yaml) | [s01…](../../implement/T-HUB-011-analyze-pre-implement/s01-analyze-schema-back-workflow-lean-detection.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-front-integ-analyze-slash-mainrule.yaml](s02-front-integ-analyze-slash-mainrule.yaml) | [s02…](../../implement/T-HUB-011-analyze-pre-implement/s02-front-integ-analyze-slash-mainrule.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-wire-decompose-implement-finish-doc-router-paths.yaml](s03-wire-decompose-implement-finish-doc-router-paths.yaml) | [s03…](../../implement/T-HUB-011-analyze-pre-implement/s03-wire-decompose-implement-finish-doc-router-paths.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-refs-dry-run-fixture-docs-role-command.yaml](s04-refs-dry-run-fixture-docs-role-command.yaml) | [s04…](../../implement/T-HUB-011-analyze-pre-implement/s04-refs-dry-run-fixture-docs-role-command.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅` (= shard `yes (CR-…) — **closed**`)  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`
