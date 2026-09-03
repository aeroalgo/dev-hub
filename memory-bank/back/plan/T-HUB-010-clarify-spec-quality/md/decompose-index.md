# Реестр шагов — T-HUB-010 clarify-spec-quality

**Plan ID:** T-HUB-010  
**План:** [plan/T-HUB-010-clarify-spec-quality/md/plan.md](../plan/T-HUB-010-clarify-spec-quality/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-23  
**Режим:** BACK DECOMPOSE  
**Эпик:** Внедрение CLARIFY workflow + `[НУЖНО УТОЧНИТЬ]` маркеров + WHAT/HOW шаблонов планов

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.** `index.md` status — best-effort зеркало.  
> **`index.yaml` contract:** `schema: epic-decompose-index/v1`, корневой список `steps:`, у шага минимум `id`, `file`, `title`, `next_phase`, `status`.  
> Plan не дублирует чеклист шагов. `implement/index.md` не создавать.

---

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | Структура workflow/lean файлов, шаблонов |
| `brainstorming` | Проработка таксономии вопросов clarify (DECOMPOSE-only) |

**Per-step:** Core(4) = `tdd` · `python-testing-patterns` · `modern-python` · `python-anti-patterns` — для шагов с Python (docs-only шаги → `impl: []`).  
Ситуативные: `python-type-safety` (шаблоны с типизированными полями), `python-configuration` (settings gate).

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг или явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| **FR-1** | `workflow-clarify.mdc` для BACK + FRONT/INTEG (или shared + stubs) | s01 + s02 | s01 = BACK + shared core; s02 = FRONT/INTEG stubs |
| **FR-2** | `BACK\|FRONT\|INTEG CLARIFY` в mainrule.mdc + role mainrule indexes + multi-word table | s04 | |
| **FR-3** | `.claude/commands/{back,front,integ}-clarify.md` | s02 | slash файлы вместе с FRONT/INTEG workflows |
| **FR-4** | Артефакт `memory-bank/{role}/clarify/clarify-YYYYMMDD-<slug>.md` по шаблону | s01 | шаблон `.cursor/templates/clarify.md` создаётся в s01 |
| **FR-5** | Процесс: таксономия → ≤5 Q sequential → Q→A → patch draft | s01 | закрыт содержимым `workflow-clarify.mdc` |
| **FR-6** | Правило `[НУЖНО УТОЧНИТЬ]` вместо silent assumption; plan workflow + lean gate | s04 | lean gate в `_lean/clarify.mdc` × ролей; mainrule |
| **FR-7** | `plan.md` содержит User Stories + Independent Test + FR-### + SC-### + WHAT/HOW | s03 | |
| **FR-8** | `integration-plan.md` — WHAT-поля адаптированы (не ломая portal inventory) | s03 | |
| **FR-9** | `workflow-*-plan.mdc` ×3: clarify gate; PLAN не закрывается при CRITICAL без resolve | s04 | |
| **FR-10** | `memory-bank-paths.mdc` — строка Clarify в таблицах back/front/integration | s04 | |
| **FR-11** | `refs/speckit-adapt-010.md` — telegraph adapt note | s05 | |
| **FR-12** | Parity `.agents/skills/role-command` sync note | s05 | sync SKILL.md если менялся role-command; проверка при s04 |
| **NFR-1** | Clarify UX = 1 вопрос за ход; итог = compact Completion Report | s01 | закрыт workflow |
| **NFR-2** | WHAT-секция не telegraph-cap; HOW/tech как сейчас | s03 | проверяется в шаблоне plan.md |
| **NFR-3** | Lean load CLARIFY = только clarify artifact + activeContext | s01 | lean gate в `_lean/clarify.mdc` |
| **NFR-4** | Язык артефактов memory-bank: RU | s01 + s03 | шаблоны и workflow — RU |
| **NFR-5** | Do Not Touch: `spec-kit/` дерево; loop runtime; epic_resolve schema | out_of_scope | все шаги — read-only для spec-kit |
| **AC+ #1** | `rg 'CLARIFY' mainrule.mdc back/mainrule.mdc` → есть команда | s04 | cp rg в s04 |
| **AC+ #2** | `workflow-clarify.mdc` (BACK) + FRONT/INTEG (shared или свои) + `_lean/clarify.mdc` × ролей существуют | s01 + s02 | |
| **AC+ #3** | `.cursor/templates/clarify.md` + `plan.md` содержат Independent Test + `[НУЖНО УТОЧНИТЬ` + WHAT/HOW | s01 + s03 | |
| **AC+ #4** | `.claude/commands/back-clarify.md` существует и делегирует role-command | s02 | |
| **AC+ #5** | Dry-run: «симулированный» clarify Completion Report описан в workflow Done When | s01 | |
| **AC+ #6** | `memory-bank-paths.mdc` содержит clarify path | s04 | |
| **AC+ #7** | `refs/speckit-adapt-010.md` перечисляет FORBIDDEN specify-cli | s05 | |
| **AC− #1** | Не устанавливать specify-cli / `.specify/` | all | нет инсталляции ни в одном шаге |
| **AC− #2** | Не заменять `memory-bank/` на `specs/###-feature/` | all | additive только |
| **AC− #3** | Не добавлять `/speckit.*` slash как канон | all | только `* CLARIFY` slash |
| **AC− #4** | Не внедрять ANALYZE/AUDIT в этом эпике | all | out_of_scope → T-HUB-011/012 |
| **AC− #5** | Не писать полный clone `clarify.md` 291 строк — адаптация | s01 | workflow = адаптация, не clone |
| **AC−(bf) #1** | Старые plan без WHAT-секции остаются валидны | s03 | шаблон влияет только на новые PLAN |
| **AC−(bf) #2** | Нет soft-default «угал» auth/stack при пустом prompt | s01 | закрыт workflow-правилом |

---

## Stages coverage (plan/canon → steps)

> Каждый этап черновика плана (§«До DECOMPOSE», §Компоненты/файлы, §Архитектура) → sNN.

| Этап / фаза план | Источник | sNN |
| :--- | :--- | :--- |
| Shared clarify-core + BACK workflow + lean + template clarify.md | план s01 | **s01** |
| FRONT + INTEG clarify workflows + lean + slash ×3 | план s02 | **s02** |
| plan.md + integration-plan.md WHAT/HOW/FR/SC/Independent Test | план s03 | **s03** |
| mainrule indexes + plan workflows gate + finish-doc-router + memory-bank-paths | план s04 | **s04** |
| role-command + CLAUDE touch + refs/speckit-adapt-010.md + smoke rg AC+ | план s05 | **s05** |
| QA эпика: rg AC+ dry-run, parity check | тест-стратегия плана | **s06** (самостоятельный QA-шаг) |
| activeContext + FINISH (Handoff, load_now) | workflow-decompose §7b | **s07** (финализация) |

> Note: план предлагал 5 шагов; coverage-анализ выводит 6 рабочих + 1 финализирующий = 7 шагов. Brownfield: нет. Plan advisory count — не HARD limit.

---

## Outcome map (plan → steps)

> Цель эпика: **агент не выдумывает критичные решения до PLAN**. Ambiguity помечена `[НУЖНО УТОЧНИТЬ]`; clarify-сессия снимает до 5 blockers; шаблоны plan принуждают WHAT→HOW + Independent Test + SC — фундамент для T-HUB-011/012.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Workflow `BACK CLARIFY` полностью описан: таксономия Q, ≤5, sequential, Recommended, Q→A, Completion Report | s01 |
| Шаблон `clarify.md` — канон нового артефакта `memory-bank/{role}/clarify/clarify-*.md` | s01 |
| `_lean/clarify.mdc` (BACK) = gate lean-load: только clarify artifact + activeContext | s01 |
| Shared clarify-core DRY: FRONT/INTEG — thin wrappers, не полный clone | s01 (shared-core), s02 (stubs) |
| Slash-команды `{back,front,integ}-clarify.md` + Cursor-parity | s02 |
| FRONT/INTEG workflow и lean created | s02 |
| plan.md имеет WHAT / HOW / User Stories + Independent Test / FR-### / SC-### / Assumptions / Clarifications | s03 |
| integration-plan.md адаптирован без разрушения portal inventory | s03 |
| `[НУЖНО УТОЧНИТЬ]` признан CRITICAL maker в `workflow-*-plan.mdc` × 3 — PLAN не FINISH без resolve | s04 |
| `mainrule.mdc` + role mainrule indexes индексируют CLARIFY | s04 |
| `finish-doc-router.mdc` маршрутизирует CLARIFY артефакт | s04 |
| `memory-bank-paths.mdc` включает clarify paths | s04 |
| Refs-doc перечисляет паттерны Spec Kit и FORBIDDEN specify-cli | s05 |
| Role-command parity (если SKILL.md менялся) + CLAUDE.md optional touch | s05 |
| Smoke QA: rg AC+ ×7 зелёные; dry-run clarify-completion-report структура | s06 |
| Out of scope (не в этой нарезке): ANALYZE, AUDIT severity schema, IDEA go/kill, specify-cli install | — / T-HUB-011…013 |

---

## Replacement cleanup (plan → steps)

> Эпик — **greenfield / additive**: создаём новые файлы, редактируем существующие секции (не замещаем старые поверхности).  
> Единственная «замена» — **процессная**: silent assumption в PLAN → `[НУЖНО УТОЧНИТЬ]` + CLARIFY. Это изменение текста workflow-правил, не удаление кода/entrypoints.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Silent assumption паттерн (процесс в docs) | C | `[НУЖНО УТОЧНИТЬ]` + `* CLARIFY` gate | s04 (edit workflow-plan rules) | yes | Не удаление файла — удаление поведения через edit правил |
| n/a — нет замен кода/entrypoints | — | — | — | — | greenfield |

> **Purge shard:** нет физических файлов для удаления → `*-legacy-fallback-purge` sNN не требуется. Поведенческая замена (silent→marked) выполняется inline в s04 путём edit workflow-plan.mdc × 3. `Kind C: Fallback? yes` → edit в-эпике (s04), не откладывать.

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-shared-clarify-core-back-workflow.yaml](s01-shared-clarify-core-back-workflow.yaml) — shared core + BACK workflow-clarify + lean + template | no | no | BACK IMPLEMENT | completed |
| **s02** | [s02-front-integ-clarify-slash.yaml](s02-front-integ-clarify-slash.yaml) — FRONT/INTEG wrappers + lean ×2 + slash ×3 | no | no | BACK IMPLEMENT | completed |
| **s03** | [s03-plan-templates-what-how.yaml](s03-plan-templates-what-how.yaml) — plan.md + integration-plan.md WHAT/HOW/FR/SC/Independent Test | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-mainrule-plan-gate-paths.yaml](s04-mainrule-plan-gate-paths.yaml) — mainrule ×3 + workflow-plan ×3 gate + finish-doc-router + memory-bank-paths | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-role-command-refs-claude.yaml](s05-role-command-refs-claude.yaml) — role-command parity + speckit-adapt-010.md + CLAUDE.md touch | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-qa-smoke-rg.yaml](s06-qa-smoke-rg.yaml) — QA: rg AC+ ×7 + dry-run clarify scenario | no | no | BACK QA | completed |
| **s07** | [s07-finish-activecontext.yaml](s07-finish-activecontext.yaml) — activeContext Handoff + index status update | no | no | BACK IMPLEMENT | completed |
**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅` (= shard `yes (CR-…) — **closed**`)  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`
