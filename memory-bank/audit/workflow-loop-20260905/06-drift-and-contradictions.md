# 06. Drift, противоречия и stale surfaces

## 1. Runtime instruction drift

`bin/runtime-sync --runtime codex --check` возвращает `No drift detected`.

`bin/runtime-sync --runtime claude --check` возвращает:

```text
hash_mismatch: /home/aero/PyProject/dev-hub/CLAUDE.md
```

Значит, Codex current entrypoint синхронизирован, а Claude entrypoint уже не соответствует `harness/instructions/main.md`. Сам факт hash mismatch должен быть P0 для runtime, потому что agent может читать не тот operational contract.

Рекомендация: сделать runtime entrypoints generated artifacts с явным marker/header и проверять все runtime targets одинаковым кодом. Не держать ручную вторую копию инструкций.

## 2. Прямое противоречие AGENTS и mainrule

Current runtime instruction требует:

```text
Codex → AGENTS.md; другой runtime entrypoint не читать
```

При этом `harness/cursor/rules/mainrule.mdc` в full linked chain требует читать корневой `CLAUDE.md` для каждой команды. Это конфликтует и с `AGENTS.md`, и с `prompt_builder`, который уже умеет выдавать runtime-specific `entrypoint`.

Исправить формулировку на параметризованную:

```text
прочитай entrypoint текущего runtime: AGENTS.md | CLAUDE.md | DSH.md
не читай entrypoints других runtime
```

Также убрать фразу “пропущенный Read ... не блокирует FINISH”, если это действительно hard requirement. Иначе правило само объявляет свой enforcement advisory.

## 3. Claude settings: duplicate hooks

В `.claude/settings.json` один и тот же hook подключён через два пути:

```text
python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/<hook>.py"
python3 "$CLAUDE_PROJECT_DIR/harness/hooks/<hook>.py"
```

`.claude/hooks` — symlink на `harness/hooks`, поэтому realpath одинаковый. Фактическое число команд:

| Event | Команд |
|---|---:|
| SessionStart | 2 |
| UserPromptSubmit | 2 |
| PreToolUse | 6 |
| PostToolUse | 4 |
| SubagentStart | 2 |
| SubagentStop | 2 |
| Stop | 2 |

Это не harmless duplication: hooks читают/пишут state, counters, sidecars, activeContext diagnostics. Возможны двойные retries, duplicate state writes и нестабильность при параллельных hook processes.

Исправление: оставить один путь, предпочтительно installer-owned `harness/hooks` через product symlink; generator должен canonicalize realpaths и dedupe commands до записи settings. Добавить test, который разворачивает symlinks и запрещает duplicate hook target per event/matcher.

## 4. Cursor и Claude имеют разные enforcement surfaces

`.claude/settings.json` содержит SessionStart/SubagentStart/SubagentStop/Stop и pre/post tool hooks. `.cursor/hooks.json` содержит только `preToolUse` для `Write|Edit|TabWrite`, причём `failClosed:false`.

Следствия:

- Cursor chat не получает тот же SubagentStart contract;
- Cursor subagent verdict не проходит тот же stop validation;
- Cursor stop не использует epic stop gate;
- ошибка hook parser в Cursor разрешает продолжение.

Если parity намеренно невозможна из-за runtime API, это должно быть declared capability matrix, а не скрытая асимметрия. Для critical workflow Cursor должен иметь equivalent command wrapper/CLI gate перед FINISH.

## 5. Workflow wording drift

### `.md` против `.yaml`

`shared/finish-doc-router.mdc` ещё говорит, что первый DECOMPOSE файл — `s01|e01-*.md`, а role workflows и finish block требуют YAML (`sNN/eNN-*.yaml`). Это прямое противоречие в том же finish path.

### Дублированная строка QA

В finish doc router дважды присутствует `* QA`: первая строка описывает QA artifact/BUGFIX routing, вторая — короткое `align after suite`. Неясно, какая строка canonical.

### Generic `@verify`

Workflow часто использует `@verify`, а runtime mappings требуют `verify-implement`, `verify-bugfix`, `verify-decompose`, `verify-qa`. Alias удобен для prose, но в machine transition должен использоваться exact agent id.

### BLOCKED / NEED_HUMAN

Код помечает `BLOCKED`/`NEED_HUMAN` как compatibility/deprecation split, а разные prompts и hooks используют оба варианта. Нужен один canonical terminal marker и explicit parser compatibility deadline.

### Reflection residue

Current T-HUB-060 удаляет REFLECT из core lifecycle, но сохраняются `finish_reflect`, старые tests и некоторые prompt/docs references. Это уже приводит к `ImportError`, а не только к документационному drift.

## 6. Registry/README drift

`loop/schemas/README.md` описывает несуществующий `verdict.py`, class `LoopGateVerdict` и verdict `SKIP`. Реальный код использует `gate_verdict.py`, `GateVerdictRecord`, `PASS/FAIL/BLOCKED`.

Такой README ломает onboarding и подталкивает к добавлению неправильных compatibility paths. Генерировать README/table из Python registry либо тестировать все ссылки/class names.

## 7. Silent fallback drift

`_read_project_yaml_pack()` swallowing any exception позволяет malformed project configuration незаметно перейти к env/default. Это semantic drift: selected pack ≠ executed pack.

Также разные слоя имеют разные fallback behavior:

- `resolve_workflow_pack` — fallback default;
- `full_resolve` — validates only two paths;
- `route_command` — returns `rules_mdc_rel=None` for unmatched prefix;
- prompt builder — fallback `BACK IMPLEMENT`;
- SessionStart — partial load warning.

Нужна единая policy: missing optional config may default, malformed/ambiguous/required route must fail-closed.

## 8. Как закрыть drift системно

Добавить `contract-manifest/v1`, из которого генерируются:

- runtime entrypoints;
- agent manifest/TOML;
- hook registration;
- schema registry;
- workflow route matrix;
- finish command mapping;
- docs tables.

CI checks:

```text
all declared files exist
all @ references resolve
all phase agents resolve to manifest + runtime
all schemas in prompts resolve to registry
all route commands resolve to workflow + gate
all runtime targets hash-match
no duplicate realpath hooks
```

## 9. Приоритет

| Приоритет | Исправление |
|---|---|
| P0 | duplicate Claude hooks, broken skills paths, sunset/video missing runtime contracts |
| P1 | runtime-specific entrypoint rule, Claude hash drift, Cursor parity, finish wording |
| P1 | partial REFLECT removal and malformed pack silent fallback |
| P2 | generated README, dedupe generic aliases, docs simplification |
