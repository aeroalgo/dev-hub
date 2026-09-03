# Decompose — T-HUB-016 dsh-cc-hooks-bridge

**Plan:** [plan/T-HUB-016-dsh-cc-hooks-bridge/md/plan.md](../plan/T-HUB-016-dsh-cc-hooks-bridge/md/plan.md)  
**Дата:** 2026-08-29  
**Статус очереди:** index.yaml  
**Режим:** BACK DECOMPOSE  

---

## Цель эпика

Подключить официальный Claude Code hooks bridge (`@deepseek-ai/dsh-hooks-claude-code`) ко всем `epic-*` DSH-профилям так, чтобы существующие Python hooks из `.claude/settings.json` реально вызывались при `EPIC_RUNTIME=dsh` — без переписывания логики `stop-gate` / `agent-pretool` в TypeScript. Зафиксировать известные дыры bridge в gap-матрице и передать их в T-HUB-008; добавить минимальный self-limit в stop-gate против бесконечного `continue` под DSH.

---

## Шаги очереди

| step | file | outcome-first title | status |
|------|------|---------------------|--------|
| s01 | s01-pin-research-gap-matrix.yaml | Gap matrix doc + version pin — bridge known gaps catalogued for T-HUB-008 | pending |
| s02 | s02-cc-hooks-bridge-fragment.yaml | cc-hooks-bridge Cordis fragment — settings.json hooks wired into all epic-* profiles | pending |
| s03 | s03-install-cc-hooks-script.yaml | install-cc-hooks.sh — idempotent installer applies bridge fragment to all profiles | pending |
| s04 | s04-loop-env-contract.yaml | Loop env contract — DSH_HOOKS_BRIDGE + CLAUDE_PROJECT_DIR propagation from loop.sh | pending |
| s05 | s05-stop-gate-self-limit-dsh.yaml | stop-gate DSH self-limit — prevent infinite block→continue loop when stop_hook_active=false under DSH | pending |
| s06 | s06-dsh-claude-compat-mount.yaml | dsh-claude-compat optional mount — skills/rules/commands access from .claude/ under DSH | pending |
| s07 | s07-smoke-regression-docs.yaml | Smoke + regression + README — dump-config smoke, Claude path green, bridge docs with gap→008 pointer | pending |

---

## Requirements coverage (plan → steps)

### Functional Requirements

| ID | Requirement | Covered by |
|----|-------------|------------|
| FR-001 | Pin + install `@deepseek-ai/dsh-hooks-claude-code` в hub (`dsh/plugins/` vendor note или profile `dsh plugin add` script) | s02 (fragment spec), s03 (installer), s07 (docs pin) |
| FR-002 | Shared patch fragment `dsh/patches/cc-hooks-bridge.yml` с `configPath` / `projectDir` contract | s02 |
| FR-003 | `install-profiles` / new `install-cc-hooks.sh` применяет fragment ко всем `epic-*` (+ document headless) | s03 |
| FR-004 | Env: `CLAUDE_PROJECT_DIR`/`projectDir` = PROJECT_ROOT; `DEV_HUB` available для hooks requiring hub paths | s04 |
| FR-005 | Optional `dsh-claude-compat` mount (feature flag `DSH_CC_COMPAT=1` default on для epic-implement) | s06 |
| FR-006 | Gap matrix doc: updatedInput · agent_type · SubagentStop transcript · stop_hook_active · SessionStart first-turn — owner T-HUB-008 / self-limit | s01 |
| FR-007 | Python: stop-gate (или thin `stop-gate-dsh-shim`) self-limits consecutive blocks под DSH (detect via `EPIC_RUNTIME=dsh` или `DSH_HOOKS_BRIDGE=1`) | s05 |
| FR-008 | Smoke: `dsh --profile epic-implement --dump-config` lists hooks-claude-code; unit test config fragment present | s07 |
| FR-009 | Regression: Claude `settings.json` hooks unchanged; Claude loop path green | s07 |
| FR-010 | Docs в `dsh/README.md`: how bridge works, pin versions, known gaps → 008 | s07 |

### Acceptance Criteria (AC+)

| AC | Criterion | Covered by |
|----|-----------|------------|
| AC+US-001 | Stop hook invoked under fake/real DSH profile dump + hook/result log; block→continue или стир продолжения зафиксировано | s05 |
| AC+US-002 | PreToolUse matcher fires command hooks в DSH-сессии (agent-pretool.py вызван) | s02, s04 |
| AC+US-003 | compat plugin lists skill из fixture `.claude/skills` | s06 |
| AC+US-004 | Gap matrix в README совпадает с AC− bridge (≥ 5 строк, owner epic указан) | s01 |
| AC+SC-001 | hooks-claude-code в dump-config epic-implement | s07 |
| AC+SC-002 | Gap matrix ≥ 5 rows with owner epic | s01 |
| AC+SC-003 | stop self-limit unit под fake consecutive blocks | s05 |
| AC+SC-004 | Claude path tests unchanged green | s07 |

### Acceptance Criteria (AC−)

| AC | Criterion (must NOT) | Covered by |
|----|----------------------|------------|
| AC−-001 | Hooks bridge не дублирует всю логику stop-gate / agent-pretool в TypeScript | s02 (design: configPath only) |
| AC−-002 | Claude `settings.json` hooks не изменены bridge'ем | s07 (regression cp) |
| AC−-003 | dsh-claude-compat недоступность не блокирует boot (fail soft) | s06 (optional flag) |
| AC−-004 | Misconfigured configPath → loud warning, не silent fail | s02 (fragment: fail-boot if required) |
| AC−-005 | gap matrix не содержит items без owner-epic | s01 (each row → owner) |

### NFR

| NFR | Requirement | Covered by |
|-----|-------------|------------|
| NFR-1 | Zero TS rewrite — только mount точка в Cordis; все hooks остаются Python | s02 |
| NFR-2 | Greenfield additive — Claude path zero-change | s07 |
| NFR-3 | Fail-closed для epic-* profiles если required flag true | s02 |
| NFR-4 | Version pinning: DSH + bridge package pins зафиксированы | s01 (research), s07 (docs) |
| NFR-5 | Optional compat mount не блокирует если пакет недоступен | s06 |

### User Stories

| Story | Covered by |
|-------|------------|
| US-001 stop-gate срабатывает в DSH-сессии loop | s05 |
| US-002 agent-pretool / bash hooks без TS копипаста | s02 |
| US-003 skills/commands/rules из `.claude/` в DSH | s06 |
| US-004 явный список «что bridge не даёт» | s01 |

---

## Stages coverage (plan → steps)

| Этап плана | Описание из плана | step(s) |
|------------|-------------------|---------|
| s01 pin research + gap matrix doc | Исследовать совместимые версии DSH + bridge, составить gap-матрицу hook-by-hook | s01 |
| s02 cc-hooks-bridge patch fragment + install script | Создать `dsh/patches/cc-hooks-bridge.yml` с configPath; добавить в package.json профилей | s02 |
| s03 mount into epic-* profiles + dump-config smoke | Применить fragment к каждому epic-* profile через installer/patch | s03 |
| s04 loop env DSH_HOOKS_BRIDGE + PROJECT_DIR contract | Прокинуть переменные окружения из loop.sh в DSH-сессию | s04 |
| s05 stop-gate self-limit under DSH (TDD) | Добавить self-limit счётчик в stop-gate.py | s05 |
| s06 optional dsh-claude-compat mount + docs | Добавить compat плагин с feature flag | s06 |
| s07 README + regression Claude path | Docs + smoke тест + regression suite | s07 |

Все 7 этапов плана покрыты; нарезка расширена (план черновик advisoriory — итого 7 шагов, все этапы из плана 1:1 атомизированы).

---

## Outcome map (plan → steps)

1. **Разработчик запускает loop с EPIC_RUNTIME=dsh** → stop-gate, agent-pretool, bash-pretool вызываются без изменений Python кода → закрывают: s02, s04, s05.
2. **DSH dump-config включает dsh-hooks-claude-code** → видимая конфигурация bridge доступна для аудита → закрывает: s02, s03, s07.
3. **Gap matrix задокументирован** → T-HUB-008 имеет точный список дыр bridge с owner-epic → закрывает: s01.
4. **skills/rules/commands из .claude/ доступны под DSH** (DSH_CC_COMPAT=1) → разработчик использует workflow без миграции → закрывает: s06.
5. **Stop self-limit предотвращает бесконечный цикл** → нет silent infinite Stop continue под DSH → закрывает: s05.
6. **Claude path не затронут** → IDE/Claude-сессии работают без деградации → закрывает: s07.
7. **Version pins зафиксированы в dsh/README.md** → совместимость контролируется явно, unreviewed upgrade = blocker → закрывает: s01, s07.

---

## Replacement cleanup (plan → steps)

| Kind | Устаревает | Замена | step | deletes | Fallback? |
|------|-----------|--------|------|---------|-----------|
| A (delete in-epic) | Assumption «008 = full TS port of all hooks» | Bridge 016 + thin 008 | s01 (gap matrix чётко ограничивает 008 scope) | comment/note в plan-T-HUB-008 если существует | — |
| A (delete in-epic) | Silent infinite Stop continue under DSH | self-limit | s05 | нет старого файла; новый guard добавляется в stop-gate.py | — |
| A (reserved slot) | `# cc-hooks-bridge: reserved include slot for T-HUB-016` в epic-implement/cordis.patch.yml | Реальный fragment insert | s02 | comment-строка заменяется реальным include; rg verify отсутствия `reserved include slot` после s02 | — |

Все A-items — greenfield additive или comment cleanup; нет удаляемых отдельных модулей/файлов, нет Plan B shimов без follow-up.

Финальный purge: не требуется (нет legacy module chain — только greenfield additive + comment cleanup). Если s02 вводит shim placeholder — s07 checkpoint содержит rg-verify на отсутствие `reserved include slot` в cordis.patch.yml всех профилей.

---

*Проверка после Write: `wc -l index.md` ≥ 80 строк — plan-artifact gate.*

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Gap matrix doc + version pin — bridge known gaps catalogued for T-HUB-008 · [yaml](s01-pin-research-gap-matrix.yaml) | BACK IMPLEMENT | completed |
| **s02** | cc-hooks-bridge Cordis fragment — settings.json hooks wired into all epic-* profiles · [yaml](s02-cc-hooks-bridge-fragment.yaml) | BACK IMPLEMENT | completed |
| **s03** | install-cc-hooks.sh — idempotent installer applies bridge fragment to all profiles · [yaml](s03-install-cc-hooks-script.yaml) | BACK IMPLEMENT | completed |
| **s04** | Loop env contract — DSH_HOOKS_BRIDGE + CLAUDE_PROJECT_DIR propagation from loop.sh · [yaml](s04-loop-env-contract.yaml) | BACK IMPLEMENT | completed |
| **s05** | stop-gate DSH self-limit — prevent infinite block→continue loop when stop_hook_active=false under DSH · [yaml](s05-stop-gate-self-limit-dsh.yaml) | BACK IMPLEMENT | completed |
| **s06** | dsh-claude-compat optional mount — skills/rules/commands access from .claude/ under DSH · [yaml](s06-dsh-claude-compat-mount.yaml) | BACK IMPLEMENT | completed |
| **s07** | Smoke + regression + README — dump-config smoke, Claude path green, bridge docs with gap→008 pointer · [yaml](s07-smoke-regression-docs.yaml) | BACK IMPLEMENT | completed |
| **s08** | Audit remediation — live DSH dump-config evidence · [yaml](s08-audit-live-dump-config.yaml) | BACK IMPLEMENT | completed |
| **s09** | Audit remediation — execute Claude-path regression and settings stability check · [yaml](s09-audit-claude-regression.yaml) | BACK IMPLEMENT | completed |
| **s10** | Audit remediation — compat skill fixture and fail-soft smoke · [yaml](s10-audit-compat-fixture.yaml) | BACK IMPLEMENT | completed |
| **s11** | Audit remediation — configurable DSH self-limit with validated default/override · [yaml](s11-audit-self-limit-config.yaml) | BACK IMPLEMENT | completed |
| **s12** | Audit remediation — required bridge config failure diagnostic smoke · [yaml](s12-audit-required-config-diagnostic.yaml) | BACK IMPLEMENT | completed |