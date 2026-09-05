# 07. Приоритетный roadmap усиления и очистки

Ниже порядок, который закрывает сначала дыры, способные пропустить неверный transition, затем качество и поддерживаемость.

## P0 — остановить ложные green paths

### P0.1 Завершить `REFLECT` migration

Текущий worktree уже удалил reflection helpers из `harness/hooks/epic/core.py`, но `finish_reflect` и старые consumers остались. Сначала сформировать explicit migration decision:

- `REFLECT` окончательно удаляется: убрать phase registry, finish dispatch/API, exports, parser branches, old tests, docs, `activeContext` fixtures и generated contracts;
- либо вернуть временные compatibility helpers и отдельно закрыть миграцию.

Acceptance:

- `bin/pytest -q` без `ImportError` и старых REFLECT assertions;
- `rg -n "REFLECT|reflection_path|finish_reflect|find_reflection"` показывает только migration note/архив или zero active references;
- `QA pass → DONE/AUDIT` не зависит от reflection artifact.

### P0.2 Исправить canonical skill topology

Выбрать один canonical path, предпочтительно:

```text
harness/skills/<skill>/SKILL.md
.agents/skills/<skill>/SKILL.md
```

Переместить/синхронизировать nested `harness/skills/skills/*`, обновить все workflow refs, затем добавить resolver test. Не добавлять silent fallback.

Acceptance: static `@` reference check = zero missing literal skill paths.

### P0.3 Включить sunset в boundary pipeline

Добавить `SunsetReport` в registry и валидацию stop hook, или удалить machine schema contract из prompt. Предпочтительно сделать его managed search boundary:

```text
sunset JSON → strict shape → ownership/context → sidecar → parent consume
```

Acceptance: valid sunset payload проходит CLI + hook; malformed/unknown/extra payload retry/block.

### P0.4 Доделать video pack

Согласовать filesystem и router:

- role-subdirectories с файлами `workflow-plan/decompose/storyboard/edit/publish`; или
- pack `route_map` с фактическими shared files.

Добавить `verify-script/edit/publish` в manifest и mappings; описать фазы без verify (`BRIEF`, `STORYBOARD`, `SHOOT`) как explicit no-gate.

Acceptance: каждый intent pipeline command route существует; `verify_agent` существует в manifest/TOML/stop mapping.

## P1 — закрыть обходы и cross-runtime drift

### P1.1 Сделать wire schema strict

- `schema` required на external payload;
- один parser для gate/repair/sunset;
- payload `data.verdict` не является источником истины без fence;
- `extra=forbid` одинаково для всех runtimes;
- ISO timestamp/hash/agent enum validators.

Acceptance: no-fence verdict and missing schema cannot reach `record_verdict`.

### P1.2 Ввести semantic ownership validation

Gate/repair records должны быть связаны с current `epic_id`, `step_id`, `session_id`, `phase`, `agent_id`, parent evidence. `RepairResult` должен содержать parent blocker ids, changed files and verify result.

Acceptance: чужой или старый verdict даёт `semantic_ownership_mismatch`, не retry schema.

### P1.3 Убрать duplicate Claude hooks

Оставить один command per hook target/matcher после realpath canonicalization. Исправить installer/generator, а не только текущий JSON вручную.

Acceptance: generated settings and fixture tests report no duplicate realpath commands.

### P1.4 Исправить runtime entrypoint routing

`session_start_payload` передаёт `EPIC_RUNTIME` в `build_prompt_scope`; `mainrule.mdc` говорит “current runtime entrypoint” вместо hardcoded CLAUDE. Runtime sync должен проверять `AGENTS.md`, `CLAUDE.md`, `DSH.md` без stale copy.

Acceptance: each runtime gets only its own entrypoint in start inject and prompt chain.

### P1.5 Сделать full pack doctor

Проверять `rules_root`, roles, routes, `_lean` gates, phase registry, agent declarations, schemas, external tool gates and artifacts. Не принимать `ok=True`, если route unusable.

Acceptance: intentionally broken fixture fails with precise code (`pack_route_missing`, `pack_gate_missing`, `pack_agent_missing`).

### P1.6 Strict context bundle

`load_session` возвращает `ok=false` при missing required path. Optional entries должны иметь typed flag. SessionStart не должен inject-ить partial bundle как normal context.

Acceptance: missing one required load_now path blocks/degrades explicitly; no false `ok=true`.

## P2 — сократить drift и стоимость поддержки

### P2.1 Один Contract Registry

Из одного typed source генерировать agent frontmatter checks, manifest, Codex TOML metadata, `_lib.CONTRACTS`, section parser, verify mappings and docs matrix.

### P2.2 Один Transition Service

Свести `finish_implement`, `finish_qa`, `finish_bugfix`, `finish_handoff`, `finalize_step` к общей transaction/recovery pipeline с phase-specific policy.

### P2.3 Убрать legacy/fallback surface

- legacy gate parser;
- duplicate Codex collab parser;
- hardcoded agent sets;
- archive links в active graph;
- generic `@verify` в machine commands;
- ручной duplicate README schema table.

Удалять только после telemetry/test evidence и migration deadline.

### P2.4 Генерировать документацию

`loop/schemas/README.md`, agent matrix, workflow route matrix and runtime parity report должны строиться из registry. Manual prose оставить только для rationale и examples.

## Рекомендуемая sequence по PR/commit units

1. `REFLECT` consistency repair.
2. Skills topology + literal link checker.
3. Boundary registry + sunset hook + strict schema.
4. Video route/manifest parity.
5. Duplicate hooks + runtime entrypoint.
6. Context bundle strictness.
7. Ownership/repair v2.
8. Transactional finish and registry generation.

Не объединять эти изменения в один большой механический patch: каждый шаг должен иметь отдельный regression matrix.

## Definition of Done для всей системы

```text
all paths resolve
all agents declared/materialized
all schemas registered/validated
all gate records owned by current transition
all start bundles complete or explicit blocked
all finish transitions journaled/recoverable
all runtime surfaces parity-checked
all active docs have one canonical wording
full bin/pytest green
```
