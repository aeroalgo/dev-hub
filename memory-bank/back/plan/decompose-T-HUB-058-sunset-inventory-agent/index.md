# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-058-sunset-inventory-agent  
**План:** [plan-T-HUB-058-sunset-inventory-agent.md](../plan-T-HUB-058-sunset-inventory-agent.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-09-03  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-type-safety` | s01: новые Pydantic публичные типы |

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Agent sunset-inventory в harness: source md + preset + manifest | s02 | |
| FR-002 | Overlay mode=search, verdict=none, READ-ONLY tools | s02 | |
| FR-003 | Pydantic schema `loop-sunset-inventory/v1` в loop/schemas/ | s01 | |
| FR-004 | Report items: kind/symbol/path/mark/excerpt/forbidden_for_parent | s01 | |
| FR-005 | Excerpt budget HARD ≤40 строк/item | s01 | enforce в schema + prompt |
| FR-006 | Agent FORBIDDEN: HOW/dual-path/edit/out-of-scope read | s02 | prompt HARD |
| FR-007 | sunset_scope field в decompose template | s03 | |
| FR-008 | Workflow: required=true → parent spawn до prod Write | s04 | |
| FR-009 | Lean IMPLEMENT + behavior-first pointer: no deep-read obsolete | s04 | |
| FR-010 | Registry CONTRACT + alias sunset→sunset-inventory | s02 | |
| FR-011 | Cursor path: subagent_type=sunset-inventory | s05 | |
| FR-012 | Tests: schema validate + fixture ok/fail + registry discover | s01, s02 | TDD в s01 + s02 |
| FR-013 | Purge: no dual id; no prose inventory; no stale instructions | s06 | |
| NFR-001 (US-001) | JSON report mark=REPLACE, нет design keys | s01, s02 | schema + prompt |
| NFR-002 (US-002) | sunset_scope принимается validate-decompose-tree | s03 | |
| NFR-003 (US-003) | Parent spawn gate enforce (no FINISH без report) | s04 | |
| NFR-004 (US-004) | Explorer ≠ sunset-inventory (два отдельных id + contracts) | s02 | |
| AC−1 | Schema rejects HOW/design fields → ValidationError | s01 | |
| AC−2 | Нет слияния explorer/sunset в один id | s02 | |
| AC−3 | Нет optional mark / silent items на obsolete surface | s01 | mark=REPLACE literal |
| AC−4 | Нет parent replace без spawn при required=true | s04 | lean gate |
| AC−5 | Excerpt не license копировать — prompt + forbidden_for_parent | s02 | |
| SC-001 | discover_registry = sunset-inventory mode=search verdict=none | s02 | |
| SC-002 | Valid REPLACE ok; invalid → ValidationError | s01 | |
| SC-003 | Template содержит sunset_scope comment+example | s03 | |
| SC-004 | Lean/rules require spawn on required scope | s04 | |
| SC-005 | pytest green schema+registry | s01, s02 | |

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Schema / machine contract | plan §FR-003/004 | s01 |
| Agent materialize (Claude path) | plan §FR-001/002 | s02 |
| Registry + alias + CONTRACT | plan §FR-010 | s02 |
| Decompose template field | plan §FR-007 | s03 |
| Workflow gate lean/behavior-first | plan §FR-008/009 | s04 |
| Cursor/Task spawn doc | plan §FR-011 | s05 |
| Legacy purge A+B+C+I | plan §Replacement/sunset, §FR-013 | s06 |

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Parent на replace step получает JSON inventory без design pollution (US-001) | s01, s02, s04 |
| DECOMPOSE author задаёт `sunset_scope` → bounded spawn без угадывания (US-002) | s03 |
| Process contamination исключена: parent не читает as-built как template (US-003, AC−4) | s04, s06 |
| Explorer ≠ sunset-inventory — два отдельных контракта (US-004, AC−2) | s02 |
| Tests green: schema + registry (AC+2, AC+5, SC-005) | s01, s02 |
| Lean/behavior-first pointers: spawn gate enforce на required scope (AC+4, SC-004) | s04 |
| Purge Kind I instructions: нет 'сам прочитай as-built' в rules (FR-013, AC−5) | s06 |
| Cursor spawn path known (FR-011) | s05 |

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| Parent deep-read as-built как design на replace steps (process) | A | `@sunset-inventory` spawn + JSON | s06-purge | no | greenfield agent, нет code module; process replacement |
| manifest+registry entrypoint | B | new agent materialize | s02 | no | greenfield — нет старого entrypoint; scan pass |
| «можно вызвать explorer вместо sunset» на replace | C | required spawn sunset-inventory | s06-purge | yes | delete in-epic |
| prose inventory без schema | C | JSON+pydantic fail-closed | s06-purge | yes | delete in-epic |
| Lean/implement «сам прочитай as-built и пойми» на replace | I | spawn sunset-inventory pointer | s04 (rewrite), s06-purge (scan) | no | |
| behavior-first без inventory executor pointer | I | pointer на sunset-inventory spawn §3 | s04 (rewrite), s06-purge (scan) | no | |

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-pydantic-schema.yaml](s01-pydantic-schema.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-agent-registry.yaml](s02-agent-registry.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-decompose-template-scope.yaml](s03-decompose-template-scope.yaml) | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-workflow-lean-pointer.yaml](s04-workflow-lean-pointer.yaml) | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-cursor-task-sync.yaml](s05-cursor-task-sync.yaml) | no | no | BACK IMPLEMENT | completed |
| **s06** | [s06-legacy-fallback-purge.yaml](s06-legacy-fallback-purge.yaml) | no | no | BACK IMPLEMENT | completed |