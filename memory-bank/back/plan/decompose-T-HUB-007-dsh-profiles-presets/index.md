# decompose-T-HUB-007-dsh-profiles-presets / index.md

**Plan:** [plan-T-HUB-007-dsh-profiles-presets.md](../plan-T-HUB-007-dsh-profiles-presets.md)  
**Role:** BACK  
**Status tracker (canon):** [index.yaml](index.yaml)  
**Дата:** 2026-08-27  

---

## Outcome map (plan → steps)

| Outcome | Зачем | sNN |
|---------|-------|-----|
| Sync script `sync-agent-md-to-presets.py` читает `.claude/agents/*.md`, вырезает frontmatter, пишет `dsh/presets/<id>.prompt.md` | Пресеты для verify/reviewer/explorer не дублируют контент; изменения в `.claude/agents/` автоматически попадают в DSH | s01 |
| `dsh/presets/verify.prompt.md` содержит AC+ секции из `verify.md` | Subagent verify в DSH имеет тот же контракт gate, что и в Claude Code | s01 |
| `dsh/presets/reviewer.prompt.md` и `explorer.prompt.md` созданы | Полный набор gate-пресетов для IMPLEMENT/QA/AUDIT | s01 |
| `dsh/profiles/epic-implement/package.json` объявляет `dsh.profile.bundles` с subagent presets | `dsh --profile epic-implement --dump-config` показывает verify/explorer | s02 |
| `dsh/profiles/epic-implement/cordis.patch.yml` мапит `PROJECT_LOOP_IMPLEMENT_MODEL` → LLM + подключает presets | Env модель из `.claude/project.env` применяется к профилю без ручной правки patch | s02 |
| `dsh --profile epic-implement --dump-config` exits 0 в CI (skip без API key) | Smoke-тест профиля до реального запуска; AC+3, FR-8 | s02 |
| `dsh/profiles/epic-qa/` и `epic-decompose/` созданы с минимальными bundle + patch | QA использует reviewer; DECOMPOSE использует explorer (опционально) | s03 |
| Оставшиеся фазы (plan, creative, audit, bugfix, reflect) имеют stub или full профили | Полное покрытие 8 фаз из WORKFLOW.md; нет silent fallback | s04 |
| `dsh/scripts/install-profiles.sh` копирует/линкует `dsh/profiles/epic-*` в `$DSH_HOME/profiles/` | `install-profiles.sh` → `$DSH_HOME/profiles/epic-implement` существует; AC+1, FR-4 | s05 |
| `dsh/README.md` содержит таблицу 8 фаз → profile name | Документация для оператора; AC+5 | s05 |
| `loop/context_loop.py` `prepare` эмитит `dsh_profile=f"epic-{loop_phase_lower}"` | `prepare_session` возвращает `dsh_profile` по фазе; AC+4, FR-5 | s06 |
| Unit: `test_dsh_profile_mapping.py` проверяет phase → profile + sync hash | NFR-1: preset bytes track agent md; regression на маппинг | s06 |
| `dsh/patches/phase-models.yml` — shared LLM fragments | Профили включают общий патч моделей по фазам; FR-9 | s02, s03, s04 |

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.  
> Канон: `workflow-decompose.mdc` §Maximal detail.

| Req ID | Кратко | sNN\|eNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-1 | Directory `dsh/profiles/epic-implement/` with `package.json` + `cordis.patch.yml` | s02 | |
| FR-2 | Profiles minimum set: `epic-implement`, `epic-qa`, `epic-decompose` | s02, s03 | остальные — s04 |
| FR-3 | Presets: `verify`, `reviewer`, `explorer` registered on subagent provider | s01, s02, s03 | |
| FR-4 | `dsh/scripts/install-profiles.sh`: copy/link profiles into `$DSH_HOME/profiles/` | s05 | |
| FR-5 | `loop/context_loop.py` `prepare`: `dsh_profile=f"epic-{loop_phase_lower}"` | s06 | |
| FR-6 | `dsh/scripts/sync-agent-md-to-presets.py`: frontmatter strip + write `dsh/presets/<id>.prompt.md` | s01 | |
| FR-7 | Env bridge doc: table PROJECT_LOOP_* → patch id in profile | s05 | README |
| FR-8 | Smoke: `dsh --profile epic-implement --dump-config` exits 0 in CI skip without API key | s02 | |
| FR-9 | `dsh/patches/phase-models.yml` — shared LLM patch fragments | s02, s03, s04 | |
| NFR-1 | Preset prompt bytes track `.claude/agents/*.md` (sync script test) | s01, s06 | |
| NFR-2 | No secrets in repo patches — credentials via `$DSH_HOME/.credentials.yaml` | s02, s03, s04 | (doc only) |
| NFR-3 | Profiles boot without hub product code — workspace still PROJECT_ROOT | s02, s05 | |
| NFR-4 | DSH developer preview: pin `@deepseek-ai/dsh` version in README | s05 | |
| AC+1 | `install-profiles.sh` → `$DSH_HOME/profiles/epic-implement` exists | s05 | |
| AC+2 | `sync-agent-md-to-presets.py` → `dsh/presets/verify.prompt.md` contains AC+ section from verify.md | s01 | |
| AC+3 | `--dump-config` for epic-implement lists subagent preset verify | s02 | |
| AC+4 | Unit: phase `IMPLEMENT` → prepare returns `dsh_profile=epic-implement` | s06 | |
| AC+5 | Table in `dsh/README.md`: all 8 phases → profile name | s05 | |
| AC+6 | Model env `PROJECT_LOOP_IMPLEMENT_MODEL=X` documented → patch field to change | s05 | |
| AC−1 | Не дублировать spawn-hard policy enforcement (→ T-HUB-008) | — | out_of_scope |
| AC−2 | Не менять `.claude/agents/*.md` content (only consume) | s01 | (read-only) |
| AC−3 | Не require DSH для Claude default loop | s06 | (guard) |
| AC−4 | Не commit API keys | s02, s03, s04 | (doc) |

---

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана и канон-дока → sNN. Не растворять в layout.

| Этап / фаза | Источник | sNN\|eNN |
| :--- | :--- | :--- |
| Sync agent md → presets | plan §s01 | s01 |
| epic-implement profile + dump-config smoke | plan §s02 | s02 |
| epic-qa + epic-decompose profiles | plan §s03 | s03 |
| remaining phase profiles (stub minimum) | plan §s04 | s04 |
| install-profiles.sh + README | plan §s05 | s05 |
| prepare dsh_profile mapping + tests | plan §s06 | s06 |
| Profile matrix (8 phases) | plan §Profile matrix | s02–s04 |
| Preset architecture (AGENTS→SYNC→PRESETS→PROF→DSHHOME) | plan §Архитектура presets | s01, s02 |
| cordis.patch.yml sketch | plan §cordis.patch.yml sketch | s02, s03, s04 |

---

## Replacement cleanup (plan → steps)

> **HARD (brownfield replace):** каждая поверхность plan sunset **A/B/C** → ≥1 `sNN|eNN` с непустым `deletes:` (или out_of_scope + follow-up epic **уже в** roadmap).  
> Add без delete-шага в очереди = FAIL. Любая строка ≠ n/a → финальный `*-legacy-fallback-purge` в очереди. Greenfield → одна строка `n/a — нет замен`.  
> Канон: `workflow-decompose.mdc` §Replacement cleanup · @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN\|eNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `dsh/profiles/stub/` (T-HUB-006 scaffold placeholder) | A | real `dsh/profiles/epic-implement/` | s02 | no | stub содержимое заменяется реальным профилем |
| `dsh/README.md` (T-HUB-006 scaffold doc) | A | extended README с таблицей профилей | s05 | no | расширение, не удаление |
| n/a — нет замен | — | — | — | — | greenfield: пресеты, скрипты, патчи, тесты |

**Fallback?=yes** строк нет. Все замены — явные в s02 (stub → real) и s05 (README extend).

---

## Очередь шагов (BACK / FRONT)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-sync-agent-md-to-presets.yaml](s01-sync-agent-md-to-presets.yaml) | [s01…](../../implement/implement-T-HUB-007-dsh-profiles-presets/s01-sync-agent-md-to-presets.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-epic-implement-profile.yaml](s02-epic-implement-profile.yaml) | [s02…](../../implement/implement-T-HUB-007-dsh-profiles-presets/s02-epic-implement-profile.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-epic-qa-decompose-profiles.yaml](s03-epic-qa-decompose-profiles.yaml) | [s03…](../../implement/implement-T-HUB-007-dsh-profiles-presets/s03-epic-qa-decompose-profiles.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-remaining-phase-profiles.yaml](s04-remaining-phase-profiles.yaml) | [s04…](../../implement/implement-T-HUB-007-dsh-profiles-presets/s04-remaining-phase-profiles.yaml) | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-install-profiles-readme.yaml](s05-install-profiles-readme.yaml) | [s05…](../../implement/implement-T-HUB-007-dsh-profiles-presets/s05-install-profiles-readme.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-prepare-dsh-profile-mapping.yaml](s06-prepare-dsh-profile-mapping.yaml) | [s06…](../../implement/implement-T-HUB-007-dsh-profiles-presets/s06-prepare-dsh-profile-mapping.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-audit-phase-models-include.yaml](s07-audit-phase-models-include.yaml) | — | no | yes | BACK IMPLEMENT | completed |
**needs_creative:** `no` | `yes (CR-…)` | `yes (CR-…) ✅` (= shard `yes (CR-…) — **closed**`)  
**FORBIDDEN:** `yes (done)` без CR-ID · `no (CR-… closed)`
