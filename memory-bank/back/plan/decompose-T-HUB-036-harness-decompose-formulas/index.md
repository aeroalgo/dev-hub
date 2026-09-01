# Decompose: T-HUB-036-harness-decompose-formulas

**Plan:** [plan-T-HUB-036-harness-decompose-formulas.md](../plan-T-HUB-036-harness-decompose-formulas.md)  
**Status tracker:** [index.yaml](index.yaml)

## Steps queue

| ID | Title | Phase | Status |
|----|-------|-------|--------|
| **s01** | formula schema — decompose-formula/v1 Pydantic model + YAML loader · [yaml](s01-formula-schema-pydantic.yaml) | BACK IMPLEMENT | completed |
| **s02** | 3 bundled formulas — hooks-epic, loop-runtime-epic, cli-validate-epic · [yaml](s02-bundled-formulas-yaml.yaml) | BACK IMPLEMENT | completed |
| **s03** | formula-render CLI — materialize draft decompose sNN shards from formula · [yaml](s03-formula-render-cli.yaml) | BACK IMPLEMENT | completed |
| **s04** | formula-list CLI — enumerate available formulas with metadata · [yaml](s04-formula-list-cli.yaml) | BACK IMPLEMENT | completed |
| **s05** | formula validation — broken template exits 2 at render time · [yaml](s05-formula-validation-exit2.yaml) | BACK IMPLEMENT | completed |
| **s06** | tests ≥10 — render dry-run, schema validation, no-overwrite guard · [yaml](s06-tests-render-schema-overwrite.yaml) | BACK IMPLEMENT | completed |
| **s07** | DECOMPOSE workflow note — optional --formula hint documented · [yaml](s07-decompose-workflow-note.yaml) | BACK IMPLEMENT | completed |
---

## Requirements coverage (plan → steps)

| Requirement | Kind | Closed by sNN | Verify |
|-------------|------|---------------|--------|
| US-001: planner получает formula `loop-tooling`, DECOMPOSE начинается с validated structure | US | s02, s03 | `.venv/bin/pytest loop/tests/test_bundled_formulas.py::test_hooks_epic_loads -q` |
| US-002: formula validation — broken template fail at render | US | s05 | `.venv/bin/pytest loop/tests/test_formula_validation.py::test_broken_yaml_exit2 -q` |
| FR-001: Schema `loop/schemas/formula.py` — formula id, description, default_level, steps[] | FR | s01 | `.venv/bin/pytest loop/tests/test_formula_schema.py::test_decompose_formula_valid -q` |
| FR-002: Ship ≥3 formulas: hooks-epic, loop-runtime-epic, cli-validate-epic | FR | s02 | `.venv/bin/pytest loop/tests/test_bundled_formulas.py::test_all_bundled_formulas_valid -q` |
| FR-003: CLI formula-list, formula-render --formula --epic-id --slug --dry-run\|--out | FR | s03, s04 | `.venv/bin/pytest loop/tests/test_formula_render.py::test_dry_run_hooks_epic -q` |
| FR-004: Render produces index.yaml skeleton + sNN yaml from epic-step.yaml merge | FR | s03 | `.venv/bin/pytest loop/tests/test_formula_render.py::test_rendered_index_has_steps -q` |
| FR-005: Document in DECOMPOSE workflow: optional --formula hint in plan header | FR | s07 | `rg 'formula-render' .cursor/rules/back_developer/workflow-decompose.mdc` |
| FR-006: Tests: render dry-run; schema validation; no overwrite without --force | FR | s06 | `.venv/bin/pytest loop/tests/ -q --tb=line` |
| SC-001: 3 formulas render valid yaml | SC | s02, s06 | `.venv/bin/pytest loop/tests/test_formula_integration.py::test_render_all_formulas_dry_run -q` |
| SC-002: Rendered steps pass validate-decompose-tree after manual fill | SC | s03 | `.venv/bin/pytest loop/tests/test_formula_integration.py::test_render_then_tree_valid -q` |
| AC+ 1: decompose-formula/v1 schema | AC+ | s01 | `.venv/bin/pytest loop/tests/test_formula_schema.py -q` |
| AC+ 2: 3 bundled formulas | AC+ | s02 | `.venv/bin/pytest loop/tests/test_bundled_formulas.py -q` |
| AC+ 3: formula-list + formula-render CLI | AC+ | s03, s04 | `.venv/bin/pytest loop/tests/test_formula_render.py loop/tests/test_formula_list.py -q` |
| AC+ 4: DECOMPOSE workflow note | AC+ | s07 | `rg 'formula-render' .cursor/rules/back_developer/workflow-decompose.mdc` |
| AC+ 5: Tests ≥10 | AC+ | s06 | `.venv/bin/pytest loop/tests/test_formula_*.py loop/tests/test_bundled_formulas.py -q 2>&1 \| grep collected` |
| AC− (no overwrite without --force): существующий файл не перезапишется без флага | AC− | s03, s05 | `.venv/bin/pytest loop/tests/test_formula_render.py::test_no_overwrite_without_force -q` |
| AC− (invalid formula → exit 2): невалидный YAML → exit 2, не silent skip | AC− | s05 | `.venv/bin/pytest loop/tests/test_formula_validation.py::test_broken_yaml_exit2 -q` |

---

## Stages coverage (plan stages → steps)

| Plan stage / slice | Closed by sNN | Delta + key files |
|--------------------|---------------|-------------------|
| s01 formula schema | s01 | `loop/schemas/formula.py` — FormulaStep + DecomposeFormula + load_formula() |
| s02 3 formula yaml files | s02 | `loop/formulas/hooks-epic.yaml`, `loop-runtime-epic.yaml`, `cli-validate-epic.yaml` |
| s03 formula-render CLI | s03 | `loop/formula_render.py:render_formula()` + `epic_resolve.py` subcommand `formula-render` |
| s04 tests + DECOMPOSE doc | s04, s05, s06, s07 | `loop/tests/test_formula_*.py`; `workflow-decompose.mdc` §Formula hint; exit-2 guard |

---

## Outcome map (plan → steps)

| Outcome / зачем эпик | User/System effect | sNN |
|---------------------|--------------------|-----|
| Planner получает стартовую структуру decompose за одну команду | Экономия 30–60 мин на каждый новый эпик того же типа | s02, s03 |
| Typed schema `decompose-formula/v1` | Машиночитаемость формул; future tooling может валидировать и расширять | s01 |
| 3 bundled formulas из реальных эпиков | Проверенные паттерны hooks/loop/cli сразу доступны | s02 |
| CLI `formula-list` | Planner видит что доступно без чтения файлов | s04 |
| Broken formula → exit 2 | Плохой template не проходит молча; ошибка обнаруживается сразу | s05 |
| Tests ≥10 | Regression protection; CI-green | s06 |
| DECOMPOSE workflow документирован | Знания о --formula hint не теряются между сессиями | s07 |

---

## Replacement cleanup

n/a — нет замен. Greenfield: новые модули и файлы; существующие `.cursor/templates/decompose/` не заменяются, а дополняются через formula layer.
