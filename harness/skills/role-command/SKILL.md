---
name: role-command
description: "Role command parity chain — BACK/FRONT/INTEG workflow router (graphify, isolation, FINISH gates)"
---

# Role Command — Cursor parity chain

**Язык:** все user-facing сообщения — **русский** (@.claude/rules/language.md). Subagent/task prompts: добавь «ответ и отчёт пользователю — на русском».

**Тесты:** общий контракт `@.cursor/rules/shared/test-timeout.mdc`: pytest — `bin/pytest …` (300s встроен) или `timeout -k 10s 300s .venv/bin/pytest …`.

**FRONT + любой frontend:** тесты (vitest/playwright/npm test/e2e) — **только parent**. Subagent spawn → в промпт вставить HARD RULE из `@.claude/rules/front-tests-parent-only.md` / `~/.claude/rules/02-front-tests-parent-only.md`.

**Claude Code subagents:** `.claude/agents/` — `reviewer` · `verify` · `explorer` + built-in. **Обязательные gate’ы** (packed — `.claude/instructions/spawn-hard.md`): широкий codebase search → `@explorer`; FINISH + `code_changed` → `@verify`; BACK QA → `@reviewer`. IMPLEMENT с полным `files:` / `delta_paths_*` → `@explorer` **SKIP**. Прочие Agent — свободно.

Parse: `{PREFIX} {MODE}` or `{PREFIX} {MODE} FINISH`.

`ANALYZE` — однословный режим; роутинг выполняется через `workflow-analyze.mdc`, отдельная multi-word запись не нужна.

| Prefix | Role dir | Core (полный путь) | Isolation |
|--------|----------|-------------------|-----------|
| BACK | `.cursor/rules/back_developer/` | `{role_dir}mainrule-core.mdc` | `{role_dir}isolation_rules/_lean/<mode>.mdc` |
| FRONT | `.cursor/rules/front_developer/` | `{role_dir}mainrule-core.mdc` | `{role_dir}isolation_rules/_lean/<mode>.mdc` |
| INTEG | `.cursor/rules/integration_developer/` | `{role_dir}mainrule-core.mdc` | `{role_dir}isolation_rules/_lean/<mode>.mdc` |

**Нет файла** `.cursor/rules/mainrule-core.mdc` — core только внутри `*_developer/`.

Multi-word: `ARCHIVE NOW`, `ROADMAP MERGE`, `IDEA PIPELINE CONTINUE`, `INTEG GAP` (алиас `INTEGRATION GAP`), `INTEG GAP CLOSE` (алиас `INTEGRATION GAP CLOSE`), `SECURITY PLAN`, `SECURITY DECOMPOSE`, `REFACTOR PLAN`, `REFACTOR DECOMPOSE`.

## Step 0 — graphify (parity with Cursor `mainrule.mdc`)

Читай @.cursor/rules/graphify.mdc и ориентируйся по графу **до** Grep/Read по codebase — **кроме** IMPLEMENT, когда shard `files:` уже полный (тогда query до правки известных путей не обязателен).

**Обязателен** для: `IMPLEMENT` (если `files:` неполные / широкий поиск) · `TASK` · `BUGFIX` · `REFACTOR` · `QA` · **`SECURITY` execute** (`@aNN` / `S` one-shot); также `PM DISCOVER`, `TL SYNC DEV`; **brownfield** `BACK/FRONT/INTEG VAN`.

**Пропуск:** greenfield `VAN` · `PLAN` · `DECOMPOSE` · `CREATIVE` · `REFLECT` · `ARCHIVE NOW` · **`SECURITY PLAN` · `SECURITY DECOMPOSE`** · `GAP` (если только docs). CONTENT/MARKETING/SEO — пропускают. IMPLEMENT + полный `files:` / `delta_paths_*` — query skip.

**CLI (не в PATH):** всегда из **корня репо** (cwd = root; Shell `working_directory` = root). Канон только `<repo>/graphify-out/` — HARD RULE в @.cursor/rules/graphify.mdc.

```bash
.venv/bin/graphify query "<question>"
.venv/bin/graphify path "<A>" "<B>"
.venv/bin/graphify explain "<concept>"
```

Fallback на Read/Grep — только после ориентации по графу **или** после отчёта `@explorer`, или если root `graphify-out/graph.json` нет / stale. **IMPLEMENT:** shard `files:` / `delta_paths_*` полные → graphify query **не** обязателен до правки известных путей; `@explorer` **SKIP** (Gates 1b). Широкий поиск / неизвестные callers → graphify, затем `@explorer`. В промпт explorer: «сначала `.venv/bin/graphify`, затем Grep/Glob/`rg` fallback; не создавать nested graphify-out».

**После правок кода (FINISH):** из корня репо `.venv/bin/graphify update .` — см. @.cursor/rules/shared/finish-block.mdc.

## Step 0b — session

**HARD RULE:** канон — `.cursor/rules/mainrule.mdc` §Full linked chain.

- **PLAN / DECOMPOSE / brownfield VAN:** `Read` entrypoint текущего runtime (`CLAUDE.md` / `AGENTS.md`) → `mainrule.mdc` → индекс+core → workflow → Gates → `@` рекурсивно.
- **IMPLEMENT / TASK / BUGFIX / REFACTOR:** **не** рекурсивный `@`. Старт: `load_now` shard+index → `_lean/<mode>.mdc` → scope-lock → cheatsheet → `skills.impl` шага. Индекс роли и полный `workflow-implement.mdc` — только при FAIL. `token-economy-core` на IMPLEMENT **не** грузить (stub already-on).

Пропущенный Read из списка режима — gap, не блок FINISH.

1. PLAN/DECOMPOSE/VAN: **Read** `.cursor/rules/token-economy-core.mdc` §0.0–§0.15. IMPLEMENT: skip (stub).
2. FINISH / `* FINISH`: @.cursor/rules/shared/finish-block.mdc → @.cursor/rules/shared/finish-doc-router.mdc (+ graphify update если code changed). Грузить **перед FINISH**, не на старте IMPLEMENT.
3. Tool unclear → recommend: **Cursor** + fast-editing (default) | **Claude Code** + premium-coding (E2E / multi-file / **any PLAN**)

### Если MODE = PLAN (BACK/FRONT/INTEG/PM) или SECURITY PLAN / REFACTOR PLAN

**Сразу после acknowledgement** выведи в чат:

`SUSPENSION GUARD active — plan output unlimited`

- Читай `.cursor/rules/token-economy-core.mdc` §0.0 + §0.0.1 до записи артефакта (stub: @.cursor/rules/token-economy-stub.mdc)
- Lean load ≠ lean write: **не** сжимай `plan-*.md` / `gap-*.md` / `security/plan/plan-*.md` под telegraph / 200 lines / chat brief
- Research / audit / multi-P вход → `.cursor/rules/shared/workflow-plan-multi-epic.mdc`: **N эпиков** + roadmap, не один mega-plan; объяви `MULTI-EPIC PLAN — N эпиков`
- PLAN → recommend premium model; after PLAN → inline `roadmap-merge` (same session) → new chat for `* DECOMPOSE` первого эпика **canon** queue (не `* ROADMAP MERGE`)
## Step 1 — role index + core

**IMPLEMENT / TASK / BUGFIX / REFACTOR:** индекс роли **не** читать (режим уже выбран). Core `{role_dir}mainrule-core.mdc` — только если cheatsheet/Gates ссылаются на TDD/pytest runner и его нет в Gates.

**PLAN / DECOMPOSE / прочие:** читай **полные пути** (не basename без папки роли):

- индекс роли: `{role_dir}mainrule.mdc`
- core роли: `{role_dir}mainrule-core.mdc`

Примеры:  
`.cursor/rules/back_developer/mainrule.mdc`  
`.cursor/rules/back_developer/mainrule-core.mdc`

Корневой `.cursor/rules/mainrule.mdc` — только router-таблица.  
**Запрещено** открывать `.cursor/rules/mainrule-core.mdc` (такого файла нет).

## Step 2 — workflow

Шаблон (MODE в **lowercase**, **без** префикса роли):

`{role_dir}workflow-{mode}.mdc`

Для multi-word (`SECURITY PLAN`, `ARCHIVE NOW`, …) — **только** строка таблицы ниже (не `workflow-security plan.mdc`).

| Команда | Файл (канон) |
|---------|----------------|
| BACK BUGFIX | `.cursor/rules/back_developer/workflow-bugfix.mdc` |
| BACK IMPLEMENT | `.cursor/rules/back_developer/workflow-implement.mdc` |
| BACK QA | `.cursor/rules/back_developer/workflow-qa.mdc` |
| FRONT BUGFIX | `.cursor/rules/front_developer/workflow-bugfix.mdc` |
| INTEG GAP | `.cursor/rules/integration_developer/workflow-gap.mdc` |
| ARCHIVE NOW | `{role_dir}workflow-archive.mdc` |
| ROADMAP MERGE | `{role_dir}workflow-roadmap-merge.mdc` |
| SECURITY · SECURITY PLAN · SECURITY DECOMPOSE | `{role_dir}workflow-security.mdc` |
| REFACTOR · REFACTOR PLAN · REFACTOR DECOMPOSE | `{role_dir}workflow-refactor.mdc` |
| GAP CLOSE | `{role_dir}workflow-gap-close.mdc` |

**IMPLEMENT:** полный `workflow-implement.mdc` — **не** на старте (cheatsheet + Gates). Читать при FAIL / дыре coverage.

**ЗАПРЕЩЕНО угадывать:**
- `workflow-back-bugfix.mdc` / `workflow-front-*.mdc` / `workflow-integ-*.mdc`
- `workflow-BACK-bugfix.mdc`
- любой путь с удвоенным префиксом роли в имени файла

Нет файла → `Glob` `workflow-*.mdc` в `{role_dir}`, не изобретай имя. Execute steps in order.

## Step 3 — isolation (step 1a)

Читай **только** путь из строки **Gates** в `workflow-*.mdc` (копируй дословно). На IMPLEMENT это **стартовый** файл (вместе с cheatsheet + scope-lock).

Канон BACK QA:
`.cursor/rules/back_developer/isolation_rules/_lean/qa.mdc`

**ЗАПРЕЩЕНО угадывать:**
- `.cursor/rules/back_developer/_lean/qa.mdc` (пропущен `isolation_rules/`)
- любой `*_developer/_lean/...` без `isolation_rules/`

**Не** читай весь `isolation_rules_load.md` (каталог-справочник).  
Если Gates в workflow **нет** — lean не открывать. SECURITY / REFACTOR — Gates есть (`_lean/security.mdc` / `_lean/refactor.mdc`).

Level — из decompose step / plan / task shard.  
**Скиллы не грузить из isolation** — только из workflow (Step 5) / текущего shard.

## Step 4 — memory-bank

Каталог **строго** `memory-bank/` (lowercase).  
**ЗАПРЕЩЕНО:** `Memory-bank/`, `MEMORY-BANK/`.

Default (IMPLEMENT/TASK/QA/SECURITY execute): `memory-bank/activeContext.md` → `load_now` only. ONE work shard (`sNN|eNN` / task / bugfix / qa). **FORBIDDEN** полный `plan-*.md` в load_now; AC из shard / Handoff; jump `plan §N` только если Consumes требует. См. Context-session-economy §3–4 / token-economy §0.5.1.

**PLAN override:** inventory по `workflow-*-plan.mdc` (для INTEG PLAN — все portal-relevant implement + routes; для SECURITY PLAN — surfaces inventory). Не режь объём чтения «ради economy», если workflow требует полный registry.

## Step 5 — skills (lazy)

ONLY skills declared by the current workflow and its current decompose-step. Do NOT scan skills catalog. For `IMPLEMENT` / `TASK` / `BUGFIX` / `REFACTOR`: `skills.impl` из текущего shard — Read целиком до prod-кода; `impl: []` / `code_surface: docs` / Kind I-only → skip. FRONT UI: ещё `skills.design` / `skills.design_skills` до UI (`visible_ui: no` → skip). Pre-FINISH `verification-before-completion` / `requesting-code-review` **не** грузить — их закрывают finish-block + `@verify`. SECURITY execute: только Audit skills из `aNN`.

## Step 6 — execute

Follow workflow. BACK/FRONT QA → lean load §7 context-session-economy. Integration grep §0.11 token-economy before FINISH. Code modes: graphify Step 0 уже выполнен **или** skip по полному `files:`; FINISH → из корня репо `.venv/bin/graphify update .` если code changed.

## IDEA PIPELINE

@.cursor/rules/shared/workflow-idea-pipeline.mdc. Artifact: `memory-bank/idea/idea-<slug>.md`.

## Acknowledgement

`OK {PREFIX} {MODE} — начинаю`

Если MODE=PLAN или MODE=`SECURITY PLAN` или MODE=`REFACTOR PLAN` (или SECURITY/REFACTOR с args PLAN): сразу вторая строка `SUSPENSION GUARD active — plan output unlimited`, затем читай `.claude/rules/plan-artifact.md`. Artifact SECURITY: `memory-bank/{role}/security/plan/plan-*.md`.

Если MODE=DECOMPOSE (BACK/FRONT/INTEG): сразу `SUSPENSION GUARD active — decompose output unlimited`, затем `.claude/rules/plan-artifact.md` (секция DECOMPOSE) + `workflow-decompose.mdc` §Maximal detail + §Replacement cleanup.
Если MODE=VAN и brownfield (есть код/compose): сразу `SUSPENSION GUARD active — architecture map output unlimited`, затем `.cursor/rules/shared/workflow-van-brownfield.mdc` + `.claude/rules/plan-artifact.md` (architecture paths).

Перед FINISH на PLAN / SECURITY PLAN / REFACTOR PLAN: shell `wc -l` на plan-файл; TOC-only / слишком короткий → FAIL, дописать. На L2+ планах зафиксирован guard: `Review readiness` не содержит pending, а секция `qa_consumes` создана.  
Перед FINISH на brownfield VAN: architecture shards не stub-only; mermaid minimum (services + data-flow + erd|n/a).  
Перед FINISH на IMPLEMENT: @.cursor/rules/shared/finish-block.mdc — step-файл exists + Handoff шага **до** `decompose`=`completed`.

Slash-команды: `harness/claude/commands/` (shell: `.claude/commands/`). Для portal wire предпочтительно **`/integ-plan`**. Полная as-built карта — **`/integ-van`**.

## Sync note

SoT = `harness/claude/skills/role-command/SKILL.md` (shells: `.claude/skills/role-command/SKILL.md` and `.agents/skills/role-command/SKILL.md`).
