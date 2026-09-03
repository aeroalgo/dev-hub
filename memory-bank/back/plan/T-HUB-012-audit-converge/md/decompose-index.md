# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-012
**План:** [plan/T-HUB-012-audit-converge/md/plan.md](../plan/T-HUB-012-audit-converge/md/plan.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-23
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (BACK: один prod-модуль или один docs/test surface). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](../../../.cursor/templates/decompose/epic-step.yaml).

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

**Per-step:** BACK — skills gate в каждом `sNN` (`workflow-decompose.mdc`). Docs-only → `impl: []` (Core FORBIDDEN без Python).

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.  
> Канон: `workflow-*-decompose.mdc` §Maximal detail.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-1 | `epic-audit.yaml` → `epic-audit/v2`: `findings[]` (id, gap_type, severity, source_ref, evidence, remaining_work), `intent_checked`, `converged` | s01 | schema template |
| FR-2 | Сохранить `implemented` / `not_implemented` / `deviations` / leftover — map из findings или dual-write | s01 | additive + mapping rules в README |
| FR-3 | `workflow-*-audit.mdc` + `_lean/audit.mdc` ×3: Intent Inventory → Assess → Severity → Append shards → Converged/QA | s02, s03 | BACK в s02; FRONT/INTEG в s03 |
| FR-4 | Новый shard goal/plan_refs **обязан** содержать `source_ref` из finding | s01, s02, s04 | schema hint + BACK workflow + epic-step comment |
| FR-5 | CRITICAL constitution / P1 missing → в начале `not_implemented` / findings | s01, s02 | ordering rules в template + BACK workflow |
| FR-6 | Handoff: `converged: true` → `* QA`; иначе IMPLEMENT новых audit sNN → снова AUDIT | s02, s04 | workflow + finish-doc-router |
| FR-7 | Документировать границу ANALYZE (011) vs AUDIT (012) | s02, s04 | workflow boundary + refs |
| FR-8 | refs `speckit-adapt-012.md` | s04 | refs doc |
| FR-9 | Пример/фикстура documenting findings row | s01, s04 | README example + dry-run fixture |
| FR-10 | finish-doc-router: упомянуть `converged` flag | s04 | finish-doc-router.mdc + template |
| NFR-1 | Append-only для существующих completed implement files (не rewrite history) | s02, s03 | workflow FORBIDDEN rewrite |
| NFR-2 | Не git-diff / не branch compare | s02, s03 | Operating Constraints |
| NFR-3 | Token lean: inventory из plan § jumps + file paths из index | s01, s02, s03 | lean gates |
| NFR-4 | Не ослаблять legacy leftover gates | s01, s02, s03 | leftover fields retained in v2 |
| NFR-5 | Do Not Touch: specify-cli; отдельный CONVERGE command; ANALYZE read-only contract | s02, s03, s04 | boundary + refs FORBIDDEN |
| AC+ #1 | Template `epic-audit/v2` с `findings` + `converged` | s01 | |
| AC+ #2 | Все три workflow-audit описывают gap_type + severity + source_ref | s02, s03 | |
| AC+ #3 | Lean audit gates обновлены | s02, s03 | |
| AC+ #4 | Симуляция: FR без кода → finding `missing` HIGH/CRITICAL + new shard path | s04 | fixture |
| AC+ #5 | `unrequested` документирован как non-delete | s01, s02 | README + workflow |
| AC+ #6 | Converged path → next QA без пустого Convergence header | s02, s04 | workflow + finish-router |
| AC− #1 | Не удалять код по `unrequested` автоматически | s01, s02, s03 | |
| AC− #2 | Не требовать полный suite в AUDIT | s02, s03 | FORBIDDEN tests |
| AC− #3 | Не ломать v1-поля (additive) | s01 | dual-write / optional fields |
| AC− #4 | Не вводить MODE CONVERGE | s02, s03, s04 | no new command/mode |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| epic-audit v2 template + README + mapping rules | plan §До DECOMPOSE s01 · converge.md gap/severity/source-ref | s01 |
| BACK audit workflow + lean (Intent→Assess→Severity→Append→Converged) | plan §До DECOMPOSE s02 · converge.md Execution Steps 2–5 | s02 |
| FRONT + INTEG parity (workflow + lean) | plan §До DECOMPOSE s03 | s03 |
| finish-doc-router + decompose source_ref hint + refs + AC smoke fixture + doc-claim purge | plan §До DECOMPOSE s04 · Replacement A | s04 |

## Outcome map (plan → steps)

> **HARD (BACK):** не ужимать Goal/NFR плана до infra-slug. Канон: `workflow-*-decompose.mdc` §Outcome preserve.  
> **Map ≠ замена шагов:** каждый критичный outcome должен иметь **sNN в очереди** с outcome-first `title`, не только строку здесь.  
> Черновик числа шагов в plan — **advisory**; добавляй sNN пока coverage без дыр.  
> Строки: проблема/outcome → sNN. Краткий out_of_scope / follow-up — сюда же.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| AUDIT оценивает intent (FR/AC/stories + constitution) ↔ код/implement evidence, не только presence step_id | s01, s02, s03 |
| Findings с gap_type `missing\|partial\|contradicts\|unrequested` + severity + source_ref | s01, s02, s03 |
| Actionable gaps → append-only `sNN-audit-*` с обязательным `source_ref`; `unrequested` без auto-delete | s01, s02, s03 |
| `converged: true` + leftover пуст → QA; иначе IMPLEMENT→AUDIT loop | s02, s04 |
| CRITICAL constitution / P1 missing первыми в findings / not_implemented | s01, s02 |
| ANALYZE (011) vs AUDIT (012) граница явная; MODE CONVERGE не появляется | s02, s04 |
| Lean bound: plan § + shard file list; не full-repo / не git-diff / не suite | s02, s03 |
| Dry-run: FR без кода → `missing` HIGH/CRITICAL + new shard path | s04 |
| Docs, утверждавшие «AUDIT = только step_id», вытеснены; финальный rg purge | s02, s03, s04 |
| Parity BACK/FRONT/INTEG + refs `speckit-adapt-012.md` | s03, s04 |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C** → ≥1 `sNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** roadmap `.queue.yaml`).  
> Add без delete-шага в очереди = FAIL. Любая строка ≠ n/a → финальный `*-legacy-fallback-purge` в очереди. Greenfield → одна строка `n/a — нет замен`.  
> `Kind`: A=code · B=entrypoint/deploy · C=fallback. `Fallback?=yes` → deletes in-epic (не откладывать).  
> Канон: `workflow-*-decompose.mdc` §Replacement cleanup · @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Утверждения в `workflow-*-audit.mdc` / `_lean/audit.mdc`, что AUDIT = **только** presence `step_id` (без intent findings) | A | AUDIT = presence matrix ∪ intent findings (`gap_type`/`severity`/`source_ref`/`converged`) | s02, s03 | no | in-place rewrite docs/process |
| Примеры Handoff / finish-router, где next = QA только по пустому `not_implemented[]` без `converged` | A | next QA при `converged: true` **и** leftover пуст (dual-write map OK) | s04 | no | finish-doc-router |
| Остаток exclusive «только step_id» / отсутствие `converged` в канон-роутере после s02–s03 | A | финальный doc-claim purge + `rg` verify | s04 (`*-doc-claim-purge`) | no | final purge step |
| B–C entrypoints/fallbacks | — | — | — | — | n/a (docs/process; plan B/C = n/a) |

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-epic-audit-v2-template-readme-mapping.yaml](s01-epic-audit-v2-template-readme-mapping.yaml) | [s01…](../../implement/T-HUB-012-audit-converge/yaml/steps/s01-epic-audit-v2-template-readme-mapping.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-back-audit-workflow-lean-converge.yaml](s02-back-audit-workflow-lean-converge.yaml) | [s02…](../../implement/T-HUB-012-audit-converge/yaml/steps/s02-back-audit-workflow-lean-converge.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-front-integ-audit-parity.yaml](s03-front-integ-audit-parity.yaml) | [s03…](../../implement/T-HUB-012-audit-converge/yaml/steps/s03-front-integ-audit-parity.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-finish-router-refs-fixture-doc-claim-purge.yaml](s04-finish-router-refs-fixture-doc-claim-purge.yaml) | [s04…](../../implement/T-HUB-012-audit-converge/yaml/steps/s04-finish-router-refs-fixture-doc-claim-purge.yaml) | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅` (= shard `yes (CR-…) — **closed**`)  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`
