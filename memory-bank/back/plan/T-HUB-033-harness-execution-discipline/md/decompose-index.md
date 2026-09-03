# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-033-harness-execution-discipline  
**План:** [plan/T-HUB-033-harness-execution-discipline/md/plan.md](../plan/T-HUB-033-harness-execution-discipline/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-31  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (DECOMPOSE-only) |
| `python-testing-patterns` | pytest, tmp_path, fixtures |
| `python-type-safety` | CommitResult Pydantic, CheckpointRecord extension |
| `python-error-handling` | fail-closed на dirty tree / git subprocess |
| `python-configuration` | loop.sh env/config read pattern |

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | env EPIC_ATOMIC_COMMIT default 0 in hub; document 1 for product repos | s01, s04 | s01: env gate в maybe_atomic_commit; s04: project.env |
| FR-002 | loop/git_discipline.py: maybe_atomic_commit → CommitResult; fail-closed dirty | s01 | полная реализация |
| FR-003 | hook from finalize_step after mark-index-status success | s02 | patch core.py |
| FR-004 | commit message `{epic_id} {step_id}: {title}`; no AI body | s01, s02 | s01: format в git_discipline; s02: title передаётся из finalize |
| FR-005 | session_boundary field on CheckpointRecord (loop-checkpoint/v1 minor extend) | s03 | schema extend |
| FR-006 | loop.sh respects session_boundary → forces new agent invocation marker | s03 | loop.sh patch |
| FR-007 | document one-shard-one-session in back-implement cheatsheet | s04 | cheatsheet секция |
| FR-008 | tests: mock git; commit on success; skip env=0; fail dirty | s01 | test_git_discipline.py |
| AC#1 | git_discipline module + finalize hook | s01, s02 | |
| AC#2 | env gate EPIC_ATOMIC_COMMIT documented | s04 | |
| AC#3 | session_boundary checkpoint field + loop respect | s03 | |
| AC#4 | cheatsheet update one-shard-one-session | s04 | |
| AC#5 | tests with git mock/fixture repo | s01, s02, s03 | |
| SC-001 | atomic commit on finalize when enabled | s01, s02 | |
| SC-002 | no commit when EPIC_ATOMIC_COMMIT=0 | s01 | |
| SC-003 | session_boundary set | s03 | |
| US-001 | operator: atomic commit per sNN = git log timeline | s01, s02 | |
| US-002 | platform: opt-out via env, ad-hoc mode без commits | s01 | env gate |
| US-003 | parent: checkpoint flag session_boundary after finalize | s03 | |

---

## Stages coverage (plan/canon → steps)

> Каждый этап/фаза плана → sNN.

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| git_discipline модуль + CommitResult + env gate | Plan §HOW, FR-002 | s01 |
| Тесты git_discipline (mock git, dirty tree, skip) | Plan FR-008 | s01 |
| finalize_step hook → maybe_atomic_commit | Plan FR-003 | s02 |
| Интеграционные тесты finalize + git mock | Plan FR-008, AC#5 | s02 |
| CheckpointRecord.session_boundary schema extend | Plan FR-005 | s03 |
| loop.sh session_boundary detection | Plan FR-006 | s03 |
| Тесты session_boundary (schema + finalize write + loop.sh) | Plan SC-003 | s03 |
| Docs cheatsheet one-shard-one-session | Plan FR-007 | s04 |
| project.env EPIC_ATOMIC_COMMIT=0 documented | Plan FR-001 | s04 |

---

## Outcome map (plan → steps)

> **HARD:** не ужимать Goal/NFR плана до infra-slug. Строки: outcome → sNN.

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Operator: git log = epic timeline (US-001) | s01, s02 |
| Hub default: нет автоматических коммитов (EPIC_ATOMIC_COMMIT=0) | s01, s04 |
| Product repos: включить EPIC_ATOMIC_COMMIT=1 и получить atomic commits per sNN | s01, s02, s04 |
| Fail-closed: dirty unrelated files блокируют commit (FR-002) | s01 |
| Commit message трейсируемый: `{epic_id} {step_id}: {title}` (FR-004) | s01, s02 |
| Loop не reuse чат после finalize — session_boundary gate (US-003, FR-006) | s03 |
| Checkpoint schema расширен без breaking change (FR-005) | s03 |
| Dev знает правило одного шарда из cheatsheet при каждом BACK IMPLEMENT (FR-007) | s04 |
| Out of scope (не в этой нарезке) | — |
| auto-push / remote git ops | Deferred: не планируется |
| full loop-runner архитектурная смена | Deferred: follow-up |

---

## Replacement cleanup (plan → steps)

> Greenfield эпик — новые файлы, расширение существующих без удаления поверхностей.

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| n/a — нет замен | — | — | — | — | greenfield; CheckpointRecord.metadata extra='allow' позволяет добавить поле без breaking change; loop.sh получает новую ветку без удаления старой |

---

## Очередь шагов (BACK)

| step_id | title & файл | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [git_discipline модуль — atomic commit per sNN](s01-git-discipline-module.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [finalize_step hook — вызов maybe_atomic_commit](s02-finalize-step-hook.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [session_boundary checkpoint field + loop.sh gate](s03-session-boundary-schema.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s04** | [Cheatsheet + EPIC_ATOMIC_COMMIT в project.env](s04-docs-env.yaml) | no | no | BACK IMPLEMENT | completed |