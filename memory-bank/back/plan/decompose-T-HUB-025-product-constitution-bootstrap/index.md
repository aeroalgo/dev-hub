# [T-HUB-025 | product-constitution-bootstrap] DECOMPOSE index

**Plan:** [plan-T-HUB-025-product-constitution-bootstrap.md](../plan-T-HUB-025-product-constitution-bootstrap.md)  
**Дата:** 2026-08-31  
**Статус:** pending → s01  
**Tracker:** [index.yaml](index.yaml)

---

## Goal

Product repo получает адаптируемый constitution за одну fail-closed команду
(`seed-constitution`); workflow явно требует его для L2+ epics без silent skip ANALYZE
authority check. Greenfield tooling поверх существующего шаблона `.cursor/templates/constitution.md`.

---

## Steps

| Step | Title | Phase | Status |
|------|-------|-------|--------|
| [s01](s01-constitution-seed-cli.yaml) | Seed CLI: `constitution_seed.py` + epic_resolve wire | BACK IMPLEMENT | pending |
| [s02](s02-hub-root-guard-force.yaml) | Hub-root guard + `--force` overwrite semantics | BACK IMPLEMENT | pending |
| [s03](s03-van-checklist-techcontext.yaml) | VAN checklist bullet + techContext onboarding doc | BACK IMPLEMENT | pending |
| [s04](s04-pytest-suite-fixtures.yaml) | pytest suite + tmp_path product fixtures | BACK IMPLEMENT | pending |

---

## Requirements coverage (plan → steps)

### User Stories

| Req | Суть | sNN | Note |
|-----|------|-----|------|
| US-001 | Разработчик получает constitution одной командой | s01, s04 | seed CLI + green test |
| US-002 | Fail-closed без --force при существующем файле | s02, s04 | guard + exit 2 test |
| US-003 | PM/VAN: checklist «constitution adapted?» для L2+ | s03 | VAN мdc bullet |

### Functional Requirements

| Req | Суть | sNN | Note |
|-----|------|-----|------|
| FR-001 | Subcommand `seed-constitution` в `epic_resolve.py` | s01 | CLI wire |
| FR-002 | Source template: `.cursor/templates/constitution.md` из hub | s01 | resolve hub root |
| FR-003 | Target: `$PROJECT_ROOT/memory-bank/constitution.md` only | s01, s02 | path guard |
| FR-004 | Fill placeholders: version/date/scope из dirname | s01 | template render |
| FR-005 | Pre-fill MUST-1..9 из hub starter wording | s01 | copy defaults |
| FR-006 | Fail-closed: missing template → exit 2; missing memory-bank → create | s01 | error paths |
| FR-007 | VAN brownfield: bullet L2+ constitution gate | s03 | mdc edit |
| FR-008 | workflow-analyze-core: note pass when file exists (already spec) | s03 | doc note |
| FR-009 | Unit tests `loop/tests/test_seed_constitution.py` | s04 | TDD |
| FR-010 | `memory-bank/techContext.md`: document seed command | s03 | doc edit |
| FR-011 | Anti-mix: refuse hub root cwd without `DEV_HUB_CONSTITUTION_SEED=1` | s02 | env guard |

### Acceptance Criteria AC+

| AC+ | Criterion | sNN | Note |
|-----|-----------|-----|------|
| AC+1 | `seed-constitution --help` documented | s01 | argparse help |
| AC+2 | Product fixture: constitution ≥9 MUST sections | s01, s04 | render + test |
| AC+3 | Existing file protected without `--force` | s02, s04 | guard + exit 2 |
| AC+4 | Hub root blocked by default | s02, s04 | env guard + test |
| AC+5 | VAN workflow checklist item added | s03 | mdc bullet |
| AC+6 | techContext documents seed command | s03 | doc |

### AC−

| AC− | Constraint | sNN | Note |
|-----|-----------|-----|------|
| AC−1 | Не перезаписывать hub `memory-bank/constitution.md` случайно | s02 | hub root guard |
| AC−2 | Не auto-translate MUST per product stack (v1) | — | out_of_scope: future v2 |
| AC−3 | Не require constitution для L1 TASK/BUGFIX | s03 | VAN bullet явно «L2+» |
| AC−4 | Не блокировать loop если constitution missing | s03 | warn only, not gate |
| AC−5 | Не дублировать T-HUB-013 template изменения | — | out_of_scope: reuse as-is |

### SC (Success Criteria)

| SC | Измеримо | sNN |
|----|----------|-----|
| SC-001 | Seed создаёт валидный файл на empty product fixture | s01, s04 |
| SC-002 | `--force` required для перезаписи | s02, s04 |
| SC-003 | Hub root protected по умолчанию | s02, s04 |
| SC-004 | `loop/tests/` зелёный | s04 |

---

## Stages coverage (plan канон → steps)

| Этап плана | sNN закрывает |
|-----------|--------------|
| 1. `constitution_seed.py` + CLI wire | s01 |
| 2. Hub root guard + `--force` semantics | s02 |
| 3. VAN checklist + techContext | s03 |
| 4. pytest suite + fixtures | s04 |

---

## Outcome map (plan → steps)

| User / system outcome | Что это даёт | sNN |
|----------------------|-------------|-----|
| Разработчик продукта bootstrap constitution за одну команду | Снимает ручной copy-paste; governance явная | s01 |
| ANALYZE pass 6 работает, а не молча skipped | MUST violations видны в findings | s01 (file exists trigger) |
| Loop не затирает адаптированный constitution | Идемпотентное повторение VAN без риска | s02 |
| Hub canonical constitution никогда не перезаписан | Anti-mix защита | s02 |
| VAN checklist явно требует constitution для L2+ | Governance без «а где у нас constitution?» | s03 |
| techContext документирует bootstrap onboarding | Новый разработчик знает команду | s03 |
| Pytest green на три ключевых сценария | CI fail-closed на регрессию | s04 |

---

## Replacement cleanup (plan → steps)

Greenfield tooling — нет замен существующих путей/символов.

n/a — нет замен.

---

## Notes

- No CREATIVE — план чёткий, алгоритм прямой.
- Skills: `python-testing-patterns` · `python-configuration` · `python-error-handling` (core + s09-s11).
- After s04 — BACK ANALYZE (soft tip), затем IMPLEMENT.

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Seed CLI: constitution_seed.py + epic_resolve wire · [yaml](s01-constitution-seed-cli.yaml) | BACK IMPLEMENT | completed |
| **s02** | Hub-root guard + --force overwrite protection · [yaml](s02-hub-root-guard-force.yaml) | BACK IMPLEMENT | completed |
| **s03** | VAN checklist bullet + techContext onboarding doc · [yaml](s03-van-checklist-techcontext.yaml) | BACK IMPLEMENT | completed |
| **s04** | pytest suite + tmp_path product fixtures · [yaml](s04-pytest-suite-fixtures.yaml) | BACK IMPLEMENT | completed |