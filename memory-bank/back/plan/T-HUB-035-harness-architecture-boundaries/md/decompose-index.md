# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-035-harness-architecture-boundaries  
**План:** [plan/T-HUB-035-harness-architecture-boundaries/md/plan.md](../plan/T-HUB-035-harness-architecture-boundaries/md/plan.md)  
**Machine index:** [index.yaml](index.yaml) — **канон status**  
**Дата:** 2026-08-31  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача. Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.  
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | pytest boundary / ratchet suite |
| `architecture-patterns` | layer contract design |

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | boundaries.yaml ≥5 contracts | s01 | produce: tests/architecture/boundaries.yaml |
| FR-002 | checker CLI/API reads yaml, reports violations | s01 | produce: check_boundaries.py |
| FR-003 | ratchet: store count, fail if new > stored | s02 | produce: ratchet.json + check_ratchet() |
| FR-004 | clear error message with ratchet hint | s02 | 'RATCHET EXCEEDED: found N, allowed M' |
| FR-005 | update-ratchet CLI to refresh baseline | — | **out_of_scope**: optional, follow-up after IMPLEMENT |
| FR-006 | remediation hint in violation message | s01 | included in violation output format |
| FR-007 | doctor integration warn | s03 | optional; loop/incidents/doctor.py |
| US-001 | CI fail on new cross-layer import | s01 + s02 | pytest suite + ratchet gate |
| US-002 | ratchet tolerated legacy, gradual tightening | s02 | RatchetResult pass if ≤ stored |
| AC+1 | boundaries.yaml with ≥5 contracts | s01 | cp1 verify |
| AC+2 | check CLI works in CI | s01 | cp4 pytest suite |
| AC+3 | ratchet mechanism tested | s02 | SC-003 covered |
| AC+4 | architecture overview updated | s04 | §Layer enforcement + index shard |
| SC-001 | known-good tree stays green | s01 | test_clean_tree_no_violations |
| SC-002 | synthetic violation fails | s01 | test_synthetic_violation_detected |
| SC-003 | ratchet blocks increase | s02 | test_ratchet_increase_blocked |
| NFR-001 | check runs < 5s for hub tree | s01 | rg/ast-based (не full import loading) |
| NFR-002 | yaml schema documented | s01 | comment в boundaries.yaml + verify schema test |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Определить контракты слоёв (boundaries.yaml) | plan §Нарезка s01 | s01 |
| Checker module: читает yaml, находит violations | plan FR-002 | s01 |
| Pytest suite (AC+/AC−, SC-001, SC-002) | plan §AC, §SC | s01 |
| Ratchet json + check_ratchet() | plan §Нарезка s02, FR-003/004 | s02 |
| Ratchet pytest (SC-003, increase/decrease) | plan SC-003 | s02 |
| Doctor WARN integration | plan §Нарезка s03, FR-007 | s03 |
| Architecture doc update (overview + index) | plan §Нарезка s04, AC+4 | s04 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| CI fail on любой новый cross-layer import (US-001) | s01 (checker), s02 (ratchet gate) |
| Ratchet: legacy tolerated, gradual tightening (US-002) | s02 |
| Platform может видеть violations в `loop doctor` (FR-007) | s03 |
| Developer discovery: где находится enforcement (AC+4) | s04 |
| Нет hand-crafted enforcement до эпика (gap закрыт) | s01 — первый commit этого механизма |
| Out of scope (не в нарезке) | update-ratchet CLI (FR-005 optional) — follow-up |

---

## Replacement cleanup (plan → steps)

n/a — нет замен

Эпик greenfield: boundary enforcement не существовал; нет старых файлов/модулей/entrypoints для удаления. Никакой brownfield замены.

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-boundaries-yaml-checker.yaml](s01-boundaries-yaml-checker.yaml) boundaries.yaml + check_boundaries.py + test suite | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-ratchet-ci-test.yaml](s02-ratchet-ci-test.yaml) ratchet.json + check_ratchet() + test_ratchet.py | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-doctor-integration-warn.yaml](s03-doctor-integration-warn.yaml) loop/incidents/doctor.py + test extension | no | yes | BACK IMPLEMENT | completed |
| **s04** | [s04-architecture-doc-pointer.yaml](s04-architecture-doc-pointer.yaml) overview.md + index.md §Layer enforcement | no | no | BACK IMPLEMENT | completed |