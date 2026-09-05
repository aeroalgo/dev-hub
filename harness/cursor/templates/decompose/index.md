# Реестр шагов (Decompose index)
**Plan ID:** <plan_id>
**План:** [plan.md](plan.md)
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**
**Дата:** YYYY-MM-DD
**Режим:** BACK DECOMPOSE | FRONT DECOMPOSE | INTEG DECOMPOSE

Каждый шаг — атомарная задача (BACK/FRONT: один prod-модуль или один test-file; INTEG: один UI-элемент). Shard: `sNN|eNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/<plan_id>/md/decompose-index.md`. Machine = `plan/<plan_id>/yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · `yaml/index.md` · `yaml/index.yaml` · дубль имён.
> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `yaml/decompose-index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `decompose-index.yaml` only.** `decompose-index.md` status — best-effort зеркало (`mark-index-status` / `finalize-step` / auto `repair-index-mirror` на prepare).
> **`decompose-index.yaml` contract:** `schema: epic-decompose-index/v1`, корневой список `steps:`, у шага минимум `id`, `file` (basename в `yaml/steps/`), `title`, `next_phase`, `status`. `queue:` / `step_id:` в корне индекса недопустимы.
> `--decompose` = `decompose-index.md` | `decompose-index.yaml` | каталог эпика | shard yaml. Не передавать implement-шард.
> PLAN / другой чат **не** пишет весь этот файл и **не** трогает status, пока эпик в IMPLEMENT/loop.
> Рассинхрон → `repair-index-mirror` (rebuild queue из yaml). Состав yaml из md → `sync-index-yaml` (bootstrap).
> Plan не дублирует чеклист шагов. `implement/index.md` не создавать.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `query-builder` | INTEG: list/filter endpoints |

**Per-step:** BACK/FRONT — skills gate в каждом `sNN` (`workflow-decompose.mdc`). INTEG — lean §Contract в `eNN`, без gap/contracts as input.

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR (или UI AC для FRONT/INTEG) → ≥1 шаг, иначе явный `out_of_scope` + `follow_up: T-…` **уже в** `roadmap-*.queue.yaml`.  
> **FR verbatim (HARD):** колонка **Plan FR text** = дословный текст / nouns из `plan-*.md` (не «Кратко: два файла»). Remap FR = FAIL ANALYZE (`layout_dilution`).  
> Notes `deferred`/`partial` без `follow_up: T-…` = FAIL (`validate-decompose-tree`).  
> Канон: `workflow-*-decompose.mdc` §Maximal detail · behavior-first §1a.

| Req ID | Plan FR text (verbatim) | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | <дословно из plan> | s0N | |
| AC+ #1 | <дословно> | s0N | |
| NFR-01 | <дословно> | s0N | |
| Out of scope | <дословно> | — | follow_up: T-HUB-0NN-… |

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока (миграции, async-architecture stages, test groups) → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Зафиксировать границы | async-architecture §11.1 | s0N |
| Queue contract | plan §… | s0N |
| Перенос длинных путей | … | s0N |

## Outcome map (plan → steps)

> **HARD (BACK/FRONT):** не ужимать Goal/NFR плана до infra-slug. Канон: `workflow-*-decompose.mdc` §Outcome preserve.  
> **Map ≠ замена шагов:** каждый критичный outcome (latency, lifecycle, execution matrix, existing-services wire) должен иметь **sNN в очереди** с outcome-first `title`, не только строку здесь.  
> Черновик числа шагов в plan — **advisory**; добавляй sNN пока coverage без дыр.  
> Строки: проблема/outcome → sNN|eNN. Краткий out_of_scope / follow-up — сюда же.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| <почему эпик / user\|system outcome> | s01, s0N… |
| <execution matrix / lifecycle / latency> | s0N… (отдельные sNN, не только layout) |
| <NFR-… / AC+ #…> | s0N… |
| Out of scope (не в этой нарезке) | — / follow-up epic |

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C/I** → ≥1 `sNN|eNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** roadmap `.queue.yaml`).  
> Completeness ladder: **add → wire → enforce → purge** (behavior-first §3). Add-only на sole-path FR = FAIL (`optional_sot`).  
> Drop prod/контракта → `deletes:` **обязан** включать obsolete tests **и** Kind I instruction rewrites. Любая строка ≠ n/a → финальный `*-legacy-fallback-purge` в очереди с **`sunset_inventory` + `grep_control` по каждой строке** (шаблон: `legacy-purge-step.yaml`). Greenfield → одна строка `n/a — нет замен`.  
> `Kind`: A=code · B=entrypoint/deploy · C=fallback · **I=instruction surface**. `Fallback?=yes` → deletes in-epic (не откладывать).  
> AUDIT: обязателен `sunset_inventory_scan` + `sot_enforce_scan` на boundary FR; пустой leftover только после scan pass. Leftover asserts / instructions на sunset-контракт = FAIL.  
> Канон: `workflow-*-decompose.mdc` §Replacement cleanup · @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc · @.cursor/rules/shared/workflow-behavior-first.mdc

| Устаревает (path / symbol) | Kind (A\|B\|C\|I) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `path/or/Symbol` | A | новое API/модуль | s0N | no | или follow-up ID |
| compose `legacy-svc` command | B | новый service | s0N-purge | no | |
| `or "http://127.0.0.1:…"` | C | fail-closed settings | s0N-purge | yes | |
| инструкция старого machine format | I | инструкция нового SoT | s0N-purge | no | |
| n/a — нет замен | — | — | — | — | greenfield |

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-<slug>.yaml](s01-<slug>.yaml) | [s01…](../../implement/implement-<plan_id>/s01-<slug>.yaml) | no | yes | BACK/FRONT IMPLEMENT | pending |

**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅` (= shard `yes (CR-…) — **closed**`)  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`

## Очередь элементов (INTEG)

| step_id | title & element | implement | route | API | tdd | next_phase | status |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **e01** | [e01-<slug>.yaml](e01-<slug>.yaml) | [e01…](../../implement/implement-<plan_id>/e01-<slug>.yaml) | `/` | none | no | INTEG IMPLEMENT | pending |
