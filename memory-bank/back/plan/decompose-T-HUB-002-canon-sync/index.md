# Реестр шагов — decompose-T-HUB-002-canon-sync
**Plan ID:** T-HUB-002
**План:** [plan-T-HUB-002-canon-sync.md](../plan-T-HUB-002-canon-sync.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-22
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача редактирования doc/rules/commands (hub tooling, нет Python-кода продукта).
Shard: `sNN-<slug>.yaml` — каждый правит конкретные файлы канона.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.** `index.md` status — best-effort зеркало.
> `--decompose` = `index.md` | `index.yaml` | каталог | shard yaml рядом.

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |

Шаги — docs-only (нет Python-кода) → `impl: []` (пустой список Core).

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| AC+ #1 | Агент находит `activeContext.md` Handoff именно в `activeContext.md`, не в `implement-*.yaml` | s01 | CLAUDE.md §FINISH wording |
| AC+ #2 | Spawn вызывается через `spawn-hard.md` pointer, не самостоятельная политика L1–L2 | s01 | CLAUDE.md §context economy spawn wording |
| AC+ #3 | `front-tests-parent-only.mdc` существует в `.cursor/rules/` и ссылка из CLAUDE.md корректна | s02 | create .mdc + rg sweep |
| AC+ #4 | Все ссылки `@.cursor/rules/…` и `@.claude/…` в CLAUDE.md разрешаются без 404 | s02 | rg broken-refs sweep |
| AC+ #5 | `.agents/skills/role-command/SKILL.md` идентичен `.claude/skills/role-command/SKILL.md` (SoT = `.claude`) | s03 | sync verify + audit |
| AC+ #6 | SECURITY step-graphify в `role-command/SKILL.md` совпадает с `graphify.mdc` allowlist | s03 | cross-file align |
| AC+ #7 | `mainrule.mdc` — PM/TL/CONTENT/MARKETING/SEO строки помечены `archived`, путь с FAIL-fast | s04 | mainrule table replace |
| AC+ #8 | Slash-команды `pm-*.md`/`tl-*.md`/`content-*.md`/`marketing-*.md`/`seo-*.md` содержат преамбулу FAIL if `_archive` missing | s04 | commands preamble patch |
| AC+ #9 | `graphify.mdc` + `mainrule.mdc` Step 0 содержат hub N/A protocol + exception INTEG PLAN | s05 | graphify.mdc new section |
| AC+ #10 | `graphify.mdc` Step 0 содержит allowlist PLAN exceptions (INTEG PLAN + brownfield VAN) | s05 | graphify.mdc exception block |
| AC+ #11 | `memory-bank/architecture/` (index или overview) содержит строку: SoT rules = `.cursor`; role-command SoT = `.claude` mirror to `.agents` | s06 | architecture note |
| AC+ #12 | `rg`-suite по всем изменённым файлам — нет битых `@`-ссылок и призраков удалённых путей | s06 | verification sweep |
| AC− #1 | Нет второй копии spawn-политики («L1–L2 без spawn» как абсолют) — только pointer | s01 | old wording removed |
| AC− #2 | Нет live-путей `@.cursor/rules/project_manager/`, `@.cursor/rules/team_lead/` и др. в mainrule без archived-маркера | s04 | replace in-epic |
| AC− #3 | Нет dual `role-command` (SKILL.md в `.agents` не опережает `.claude`) | s03 | sync, `.claude` is SoT |
| AC− #4 | Нет silent Load битого `_archive` — только FAIL-fast | s04 | commands preamble |
| AC− #5 | Нет graphify halt для INTEG PLAN / hub — только N/A protocol + inventory fallback | s05 | graphify.mdc |
| FR-1 | CLAUDE.md Session/FINISH: Handoff только в `activeContext.md` | s01 | §Session / §FINISH |
| FR-2 | CLAUDE.md spawn: pointer на `spawn-hard.md` exceptions, не абсолютный «L1–L2 без spawn» | s01 | §Context economy |
| FR-3 | `front-tests-parent-only.mdc` создан в `.cursor/rules/` (ссылка из CLAUDE.md + `.claude/rules/`) | s02 | create file |
| FR-4 | Broken `@`-refs в CLAUDE.md и rules-файлах исправлены после rg sweep | s02 | rg audit |
| FR-5 | `.agents/skills/role-command/SKILL.md` ← sync из `.claude` (SoT) | s03 | overwrite if diff |
| FR-6 | `mainrule.mdc`: PM/TL/CONTENT/MARKETING/SEO → archived + FAIL | s04 | table edit |
| FR-7 | Slash pm-*/tl-*/…: FAIL preamble без `_archive` | s04 | commands patch |
| FR-8 | `role-command/SKILL.md` SECURITY+graphify wording aligned | s03 | cross-align |
| FR-9 | `graphify.mdc` + `mainrule` Step 0: hub N/A protocol + INTEG PLAN / inventory exception | s05 | graphify.mdc + mainrule.mdc |
| NFR-1 | Hub tooling не вендорит `_archive/` полностью (YAGNI) | out_of_scope | follow-up product decision |
| NFR-2 | Cursor hooks epic parity — не этот эпик | out_of_scope | T-HUB-004+ |
| NFR-3 | Все изменения — doc-only (нет изменений Python-кода продукта) | all shards | code_surface: docs |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза плана | Источник | sNN |
| :--- | :--- | :--- |
| s01 — CLAUDE canon pass (Session/FINISH/spawn/re-read/TodoWrite/archive) | plan §черновик фаз | s01 |
| s02 — front-tests.mdc + link sweep (create mdc; rg fix broken refs) | plan §черновик фаз | s02 |
| s03 — role-command SoT (sync .agents ← .claude; align SECURITY graphify) | plan §черновик фаз | s03 |
| s04 — mainrule + archive FAIL (prefix table + commands preambles) | plan §черновик фаз, FR-6, FR-7 | s04 |
| s05 — graphify + INTEG PLAN wording + IDEA gate | plan §черновик фаз, FR-9 | s05 |
| s06 — architecture/README note + verification rg suite | plan §черновик фаз, AC+ #11, AC+ #12 | s06 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Агенты Cursor и Claude Code читают **один** согласованный канон — Handoff только в `activeContext`, spawn = pointer на `spawn-hard` | s01 |
| `front-tests-parent-only` путь существует в `.cursor/rules/` — агент не получает 404 при Step 0 | s02 |
| Все `@`-ссылки в CLAUDE.md и rules корректны — нет Ghost-путей | s02 |
| Dual `role-command` исчезает: `.claude` = SoT, `.agents` = mirror | s03 |
| SECURITY step-graphify wording согласован между `SKILL.md` и `graphify.mdc` | s03 |
| PM/TL/CONTENT/MARKETING/SEO → явный archived FAIL; агент не Load битый path | s04 |
| Slash-команды pm-*/tl-*/… = FAIL без archive; текст restore инструкции | s04 |
| Graphify Step 0 не зависает на hub (нет `graphify-out/graph.json`) — N/A protocol + INTEG PLAN inventory | s05 |
| `memory-bank/architecture/` содержит SoT-заметку о rules/role-command | s06 |
| Итоговый rg-sweep — нет битых ссылок, нет призраков | s06 |
| Out of scope: vendor `_archive/` полностью | — / follow-up product decision |
| Out of scope: Cursor hooks epic parity | — / T-HUB-004+ |

---

## Replacement cleanup (plan → steps)

> Brownfield replace: старые wording/paths → новые. Каждая строка имеет sNN с `deletes`.

| Устаревает (path / symbol / wording) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| «IMPLEMENT L1–L2 без spawn» как абсолютная политика в CLAUDE.md | A | pointer на `spawn-hard.md` + exceptions | s01 | yes | In-epic replace |
| Live `@.cursor/rules/project_manager/…` в mainrule таблице без archived | A | `archived — FAIL if _archive missing` | s04 | yes | In-epic replace |
| Live `@.cursor/rules/team_lead/…` в mainrule таблице без archived | A | `archived — FAIL if _archive missing` | s04 | yes | In-epic replace |
| Live `@.cursor/rules/content_growth/…` в mainrule без archived | A | `archived — FAIL if _archive missing` | s04 | yes | In-epic replace |
| Live `@.cursor/rules/marketing_growth/…` в mainrule без archived | A | `archived — FAIL if _archive missing` | s04 | yes | In-epic replace |
| Live `@.cursor/rules/seo_ops/…` в mainrule без archived | A | `archived — FAIL if _archive missing` | s04 | yes | In-epic replace |
| Silent Load missing archive в pm-*/tl-*/content-*/marketing-*/seo-*.md командах | A | FAIL preamble + restore инструкция | s04 | yes | In-epic replace |
| Graphify без hub N/A protocol и без INTEG PLAN exception | A | N/A section + allowlist exception | s05 | yes | In-epic replace |
| Все replaced wording — итоговый rg-purge + verify нет призраков | A+C | rg sweep | s06-legacy-fallback-purge | yes | Финальный purge |

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-claude-canon-pass.yaml](s01-claude-canon-pass.yaml) — CLAUDE.md Session/FINISH/spawn wording | no | no | BACK IMPLEMENT | completed |
| **s02** | [s02-front-tests-mdc-link-sweep.yaml](s02-front-tests-mdc-link-sweep.yaml) — create .mdc + rg broken-refs | no | no | BACK IMPLEMENT | completed |
| **s03** | [s03-role-command-sot-sync.yaml](s03-role-command-sot-sync.yaml) — .agents ← .claude sync + SECURITY align | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-mainrule-archive-fail.yaml](s04-mainrule-archive-fail.yaml) — mainrule prefix archived + commands preamble | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-graphify-hub-na-integ-plan.yaml](s05-graphify-hub-na-integ-plan.yaml) — graphify.mdc N/A protocol + INTEG PLAN exception | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-architecture-note-rg-purge.yaml](s06-architecture-note-rg-purge.yaml) — arch SoT note + legacy-fallback-purge rg suite | no | no | BACK IMPLEMENT | completed |
**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅`
