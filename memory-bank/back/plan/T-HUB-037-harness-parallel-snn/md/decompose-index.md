# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-037-harness-parallel-snn
**План:** [plan/T-HUB-037-harness-parallel-snn/md/plan.md](../plan/T-HUB-037-harness-parallel-snn/md/plan.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-09-01
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml` — [.cursor/templates/decompose/epic-step.yaml](.cursor/templates/decompose/epic-step.yaml).

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| AC+1 | depends_on в decompose index schema (optional, backward compatible) | s01 | DecomposeIndex Pydantic + backward compat cp1 |
| AC+2 | compute_ready_wave + overlap check | s01 (wave), s02 (overlap) | cp2/cp3 + test_no_overlap/test_overlap |
| AC+3 | Worktree spawn/mock integration test | s03 (pool) + s05 (integration) | cp1/cp2 subprocess mock + SC-001 cp |
| AC+4 | Env gates documented | s04 | docs/parallel-snn.md cp4: rg EPIC_PARALLEL_SNN |
| AC+5 | T-HUB-029 arm_phase integration point documented | s04 (doc) + s05 (wire) | rg arm_phase docs + transition engine hook |
| FR-001 | compute_ready_wave(index_yaml) → list[sNN] via depends_on graph | s01 | loop/parallel/wave.py + tdd cp2/cp3 |
| FR-002 | file_overlap_check(step_a, step_b) → bool | s02 | loop/parallel/overlap.py + tdd cp1/cp2 |
| FR-003 | Worktree pool: create/destroy; base = current HEAD | s03 | loop/parallel/worktree.py + tdd cp1/cp2/cp3 |
| FR-004 | Orchestrator: spawn parallel sessions max EPIC_PARALLEL_MAX default 2 | s04 | orchestrator.py cp2 wave_spawn_count |
| FR-005 | Child runs standard prepare→agent→check_after for single sNN | s04 | subprocess spawn per worktree; merge policy doc |
| FR-006 | Index status updates serialized via existing flock | s04 | orchestrator uses epic_index flock cp4 |
| FR-007 | Transition Engine: parallel mode only armed_step=IMPLEMENT + registry allows | s05 | transition hook cp1/cp3 |
| FR-008 | Tests: wave computation; overlap detection; mock spawn count; sequential fallback | s01+s02+s04+s05 | tdd lists per shard |
| US-001 | Parallel run для independent s02+s03 → 2 worktrees spawned | s04+s05 | SC-001 cp: test_sc001_two_independent_steps |
| US-002 | Fail-closed if file overlap → sequential fallback | s02+s04 | SC-002 cp: test_sc002_overlap_blocks_parallel |
| US-003 | Default sequential, opt-in only | s04+s05 | SC-003 cp: test_sequential_fallback_env + test_sc003 |
| SC-001 | Wave of 2 independent steps identified | s01+s05 | pytest test_sc001_two_independent_steps |
| SC-002 | Overlap blocks parallel | s02+s04+s05 | pytest test_sc002_overlap_blocks_parallel |
| SC-003 | EPIC_PARALLEL_SNN=0 no parallel spawn | s04+s05 | pytest test_sc003_epic_parallel_zero_unchanged |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| depends_on schema + wave compute | plan §FR-001 | s01 |
| file overlap checker (fail-closed gate) | plan §FR-002 | s02 |
| worktree pool: create/destroy | plan §FR-003 | s03 |
| orchestrator: opt-in env + spawn + flock | plan §FR-004, FR-005, FR-006 | s04 |
| transition engine wire + integration tests | plan §FR-007, FR-008, AC-5 | s05 |
| env gates documentation + merge policy | plan §AC-4, Anti-scope | s04 (docs/parallel-snn.md) |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Operator запускает IMPLEMENT с independent sNN в parallel → сокращает wall time | s01 (wave), s03 (worktree), s04 (spawn), s05 (transition hook) |
| Fail-closed при file overlap → parallel не corrupt repo | s02 (overlap check), s04 (filter pairs), s05 (SC-002 test) |
| Default sequential — opt-in только через EPIC_PARALLEL_SNN=1 | s04 (early return None), s05 (sequential branch test) |
| depends_on schema backward-compatible — существующие индексы без поля работают | s01 (backward compat cp1) |
| T-HUB-029 arm_phase integration point явно задокументирован | s04 (docs/parallel-snn.md), s05 (transition hook) |
| Index status updates сериализованы через flock — нет race condition при parallel | s04 (flock via epic_index) |
| max EPIC_PARALLEL_MAX worktrees — bounded resource | s04 (cap cp: test_max_parallel_cap) |
| Integration tests: SC-001/SC-002/SC-003 | s05 (test_parallel_integration.py) |

---

## Replacement cleanup (plan → steps)

n/a — нет замен. Greenfield: loop/parallel/ создаётся с нуля; epic_transition.py расширяется новой ветвью (не замена старой логики).

---

## Очередь шагов

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-parallel-index-schema.yaml](s01-parallel-index-schema.yaml) — `loop/parallel/wave.py`, `loop/schemas/decompose_index.py` | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-parallel-overlap-checker.yaml](s02-parallel-overlap-checker.yaml) — `loop/parallel/overlap.py` | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-worktree-pool.yaml](s03-worktree-pool.yaml) — `loop/parallel/worktree.py` | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-parallel-orchestrator.yaml](s04-parallel-orchestrator.yaml) — `loop/parallel/orchestrator.py`, `docs/parallel-snn.md` | no | yes | BACK IMPLEMENT | completed |
| **s05** | [s05-transition-engine-hook.yaml](s05-transition-engine-hook.yaml) — `loop/epic_transition.py`, `loop/tests/test_parallel_integration.py` | no | yes | BACK IMPLEMENT | completed |
**Параллельный потенциал (v1 самого эпика):** s02 и s03 не зависят друг от друга (оба depend_on s01). После реализации данного эпика их можно запускать параллельно через сам механизм T-HUB-037.
