# BUGFIX: canonical-paths-test-regression

- **Epic:** `T-HUB-062-skill-topology-canonical-paths`
- **Date:** 2026-09-06
- **Role:** BACK
- **Источник:** `memory-bank/back/qa/T-HUB-062-skill-topology-canonical-paths/qa-20260906-canonical-paths.yaml` §Fix plan (`BACK BUGFIX T-HUB-062-skill-topology-canonical-paths update test_harness_paths.py asserts to canonical harness/skills/product-discovery/SKILL.md`)
- **Skills:** `systematic-debugging`, `tdd`, `python-testing-patterns`, `python-error-handling`, `verification-before-completion`

## 1. Симптом и QA Findings
- `loop/tests/test_harness_paths.py:55: test_symlink_agents_skills_points_to_harness` упал с `AssertionError` при проверке `(ROOT / "harness" / "skills" / "skills" / "product-discovery" / "SKILL.md").exists()`.

## 2. Root Cause
- В ходе реализации эпика `T-HUB-062-skill-topology-canonical-paths` устаревший вложенный путь `harness/skills/skills/` был полностью вычищен, а все 192 скилла перемещены на канонический путь первого уровня `harness/skills/<skill-name>/SKILL.md`.
- Тест `test_symlink_agents_skills_points_to_harness` в `loop/tests/test_harness_paths.py` сохранял устаревший ассерт на вложенный путь `harness/skills/skills/product-discovery/SKILL.md`.

## 3. Решение (Fix)
- Обновлены ассерты в `loop/tests/test_harness_paths.py::test_symlink_agents_skills_points_to_harness`:
  - `(ROOT / "harness" / "skills" / "product-discovery" / "SKILL.md").exists()`
  - `(ROOT / ".agents" / "skills" / "product-discovery" / "SKILL.md").exists()`

## 4. Regression Evidence & Test Verification
- Targeted pytest: `bin/pytest loop/tests/test_harness_paths.py -q --tb=line` — 7 passed.
- Full test suite: `bin/pytest -q --tb=line` — 1975 passed, 3 skipped, 0 failed (100% green).
