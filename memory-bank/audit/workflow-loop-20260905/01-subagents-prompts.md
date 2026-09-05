# 01. Аудит subagents и системных prompt contracts

## 1. Карта источников

| Слой | Файлы | Роль |
|---|---|---|
| Prompt SoT | `harness/agents/*.md` | Полный prompt, frontmatter, tools/disallowedTools, maxTurns, overlay и human instructions |
| Claude consumer | `.claude/agents` → symlink на `harness/agents` | Claude получает markdown и frontmatter напрямую |
| Registry | `harness/manifest.yaml` | Какие agents материализуются и в какие runtime |
| Codex consumer | `.codex/agents/*.toml` | Generated name/description/developer instructions |
| Hook contract | `harness/hooks/_lib.py:CONTRACTS` | Короткий injected contract на `SubagentStart` |
| Stop enforcement | `harness/hooks/subagent-stop.py` | Verdict/repair validation, retry, state update |
| Final gate | `harness/hooks/stop-gate.py` | Можно ли parent завершить сессию/эпик |

Сейчас это шесть источников поведения. Они не генерируются из одной типизированной модели.

## 2. Инвентаризация

В `harness/agents` найдено 11 prompt-файлов:

- loop/software: `verify-implement`, `verify-bugfix`, `verify-qa`, `verify-decompose`, `analyze-verify`, `explorer`, `gate-repair`, `sunset-inventory`;
- video: `verify-script`, `verify-edit`, `verify-publish`.

В `harness/manifest.yaml` описано только 8 agents: отсутствуют `verify-script`, `verify-edit`, `verify-publish`. Поэтому parity checker формально зелёный, потому что сравнивает только agents, уже внесённых в manifest. Это не проверка всех prompt-файлов.

## 3. Findings

### P0 — manifest не покрывает video agents

`workflows/video/phase_registry.yaml` указывает:

```yaml
SCRIPT: verify-script
EDIT: verify-edit
PUBLISH: verify-publish
```

Но эти три id отсутствуют в `harness/manifest.yaml`. Следствия:

- Claude может увидеть их через symlink, если родитель вызовет agent вручную;
- Codex TOML для них не генерируется;
- registry/parity не считает отсутствие ошибкой;
- `SubagentStart` contracts не содержат этих id как finish agents;
- `SubagentStop` не относит их к `VERIFY_FINISH_AGENTS`, поэтому verdict flow для video не симметричен software flow.

Что сделать:

1. Добавить три agent definition в manifest с одинаковым runtime policy.
2. Расширить `VERIFY_MB_FINISH_SUBCMD` и phase-aware mapping для `SCRIPT`, `EDIT`, `PUBLISH`.
3. Сделать parity source-driven: множество agents берётся из `harness/agents/*.md`, а не из вручную заданного `REQUIRED_CODEX_AGENTS`.
4. Добавить e2e matrix `phase → verify_agent → prompt → stop validation → finish subcommand` для каждого workflow pack.

### P0 — Codex materialization теряет enforcement metadata

`loop/runtime_materializers/codex_agent_toml.py` генерирует только:

```toml
name = ...
description = ...
developer_instructions = ...
```

Из markdown frontmatter не переносятся `tools`, `disallowedTools`, `maxTurns`, `color`, `overlay`, `managed`, `mode`, `requires_model`, `default_loop`, `default_chat`, `verdict`, `allow_worktree`.

Это означает, что для Codex запрет Write/Edit/Agent или ограничение turns — не native configuration, а текст внутри `developer_instructions`. Текстовый запрет полезен, но не является техническим deny boundary.

Что усилить:

- описать допустимую Codex mapping для каждого поля и валидировать generated TOML;
- если Codex не поддерживает конкретное поле, явно перенести его enforcement в hook/policy layer, а не оставлять только prose;
- в generated file писать `policy_fingerprint` и `source_prompt_sha256`;
- в parity тесте проверять не только наличие TOML, но и equivalence matrix: source policy → runtime policy;
- при невозможности эквивалентного переноса помечать agent `unsupported_runtime_policy` и fail-closed, а не silently materialize урезанный agent.

### P1 — contract дублируется в prompt, `_lib.CONTRACTS` и parser

Например, для `verify-implement` обязательные секции одновременно описаны:

- в `harness/agents/verify-implement.md`;
- в `_lib.CONTRACTS`;
- в `_SECTION_PATTERNS`;
- в `subagent-stop.py` и `verify_hint.py`;
- в workflow finish block.

Дублирование уже создаёт drift: `verify-qa` имеет `pass-blocked-fail`, остальные gate prompts чаще описывают `PASS/FAIL`; alias `verify` записывается как `verify`, а `verify-implement` — как тот же logical gate; video agents вообще не включены в mapping.

Рекомендация: ввести typed `AgentContract` с полями `required_sections`, `verdict_schema`, `allowed_verdicts`, `finish_command`, `mode`, `scope`, `max_read`, `max_write`, `runtime_support`. Из него генерировать:

- frontmatter validation;
- `_lib.CONTRACTS` text;
- `_SECTION_PATTERNS`;
- `verify_hint` mapping;
- manifest/parity;
- machine-readable contract matrix.

Human prompt должен объяснять contract, а не быть вторым каноническим источником.

### P1 — sunset agent получает contract, но не получает end-to-end enforcement

`SubagentStart` содержит `sunset-inventory` contract, включая требование `loop-sunset-inventory/v1`. Однако:

- sunset не входит в `_ALWAYS_INJECT`;
- если workflow state не active, его contract вообще не inject-ится;
- `SubagentStop` имеет отдельные ветки только для `VERIFY_FINISH_AGENTS` и `gate-repair`;
- sunset verdict/result не валидируется и не сохраняется в state;
- schema отсутствует в `BOUNDARY_REGISTRY`.

Нужно выбрать один режим:

1. Sunset — настоящий managed boundary agent: добавить его в registry, validator, stop handler, retry/escalation, sidecar и finish mapping; или
2. Sunset — обычный advisory search agent: убрать обязательный JSON schema contract и не обещать machine validation.

Текущее смешанное состояние хуже обоих вариантов.

### P1 — проверяется форма, но не ownership/evidence

`GateVerdictRecord` допускает optional `step_id`, `session_id`, `epic_id`, `evidence_sha256`. `SubagentStop` проверяет schema shape, но не требует, чтобы:

- `agent_id` совпадал с фактически завершившимся agent;
- `step_id` совпадал с armed step;
- `epic_id` совпадал с active epic;
- `session_id` совпадал с текущей сессией;
- evidence hash совпадал с последним отчётом/артефактом;
- verdict был выдан после текущего prompt identity.

Сейчас часть identity проверяется позднее через state evidence, но schema record сам по себе может быть валидным и чужим по ownership.

Усиление: validator должен принимать `ExpectedGateContext` и выполнять два слоя:

```text
schema valid → semantic ownership valid → persist sidecar/state
```

Не смешивать semantic failure со schema retry: schema error можно retry-ить, ownership mismatch должен немедленно блокировать и требовать новый gate.

### P2 — hard tool policy различается между runtime

Claude markdown frontmatter перечисляет `disallowedTools`, но Codex generated TOML этого не знает. Hook policy частично защищает `PreToolUse`, но при отсутствии/ошибке hook-а поведение зависит от runtime. Нужен один policy decision point перед tool call, а не сочетание frontmatter + prose + несколько hook-ов.

## 4. Что уже хорошо и сохранять

- отдельные роли `gate`, `search`, `repair`;
- repair agent не должен сам spawn-ить verify или вызывать FINISH;
- schema retry ограничен и переводит процесс в `NEED_HUMAN`;
- prompt contracts требуют `ALLOW READ/WRITE` и named VERIFY command;
- gate agents read-only по intent;
- `GateVerdictRecord` и `RepairResultRecord` имеют `extra=forbid`;
- `verify-qa` явно допускает BLOCKED, что полезно для QA→BUGFIX.

## 5. Acceptance criteria после исправления

- каждый `harness/agents/*.md` либо materialized/declared с явной причиной исключения;
- для каждого phase registry `verify_agent` существует в manifest, prompt registry, stop mapping и generated runtime;
- generated TOML policy diff не содержит silent loss;
- contract matrix генерируется из одного source и snapshot-test проходит;
- каждый managed agent имеет positive/negative SubagentStart + SubagentStop test;
- sunset либо полностью проходит тот же pipeline, либо больше не заявляет обязательную schema validation.
