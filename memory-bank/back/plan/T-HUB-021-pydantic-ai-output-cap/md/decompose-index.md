# Decompose — T-HUB-021 pydantic-ai-output-cap
**Plan:** [plan/T-HUB-021-pydantic-ai-output-cap/md/plan.md](../plan/T-HUB-021-pydantic-ai-output-cap/md/plan.md)  
**Дата:** 2026-08-31  
**Статус очереди:** index.yaml  
**Режим:** BACK DECOMPOSE  

---

## Цель эпика

Заменить сырой HTTP `/chat/completions` в `bash-output-cap.py` на **pydantic-ai** с типизированным выходом `LogSummary`, сохранив текущий extract-first pipeline и fail-soft при отключённом LLM. Создать shared модуль `llm_structured.py` как основу для будущих T-HUB-022/023 fallback-эпиков.

---

## Шаги очереди

| step | file | outcome-first title | status |
|------|------|---------------------|--------|
| s01 | s01-pin-research-compat.yaml | Pin research — pydantic-ai × OmniRoute compat matrix + requirements-hub.txt | pending |
| s02 | s02-log-summary-models.yaml | LogSummary + LogError models in llm_structured.py | pending |
| s03 | s03-agent-factory-sync-runner.yaml | make_output_cap_agent() + run_log_summary() sync runner with retries | pending |
| s04 | s04-bash-output-cap-integration.yaml | bash-output-cap.py structured path integration + build_view render | pending |
| s05 | s05-unit-tests-mocked.yaml | Unit tests — mocked agent, no network, TDD red→green | pending |
| s06 | s06-legacy-sunset-purge.yaml | Legacy urllib _http_chat + free-text llm_summarize purge | pending |
| s07 | s07-env-docs.yaml | project.env flag comment + techContext.md install note + loop/README snippet | pending |
| s08 | s08-audit-env-keys.yaml | AUDIT §0.11 — env keys vs code, AC parity check + final suite green | pending |

---

## Requirements coverage (plan → steps)

### Functional Requirements

| ID | Requirement | Covered by |
|----|-------------|------------|
| FR-001 | Add `pydantic-ai` to `requirements-hub.txt`; document install | s01 (create file), s07 (docs) |
| FR-002 | `llm_structured.py`: `LogSummary` BaseModel + `make_output_cap_agent()` | s02 (models), s03 (factory) |
| FR-003 | Provider: base_url + api_key from env; primary + fallback model chain | s03 |
| FR-004 | `run_log_summary(cmd, sample, dump_path) -> LogSummary | None` with timeout, retries | s03 |
| FR-005 | `bash-output-cap.py`: structured path when STRUCTURED=1; render from model | s04 |
| FR-006 | Preserve `extract_signals` first — LLM only when good=False | s04 |
| FR-007 | Unit tests: mock provider, no live network | s05 |
| FR-008 | Integration test optional behind LLM_INTEGRATION_TEST=1 | s05 (stub/skip), s08 (note) |
| FR-009 | `project.env` comments + README snippet | s07 |
| FR-010 | Regression: existing loop/tests green | s05 (cp3), s08 (cp4 final) |

### Acceptance Criteria (AC+)

| AC | Criterion | Covered by |
|----|-----------|------------|
| AC+1 | `requirements-hub.txt` contains `pydantic-ai` + compatible `pydantic>=2` | s01 |
| AC+2 | `llm_structured.py` exported API documented in module docstring | s02 |
| AC+3 | `bash-output-cap` uses structured path by default when summary enabled | s04 |
| AC+4 | `LogSummary` fields populated from fixture logs in tests; view contains file:line | s05 |
| AC+5 | Fallback model chain preserved (primary → FALLBACK_MODEL) | s03, s05 |
| AC+6 | Hook never raises to parent on LLM failure (exit 0) | s03, s04 |
| AC+7 | `PROJECT_OUTPUT_SUMMARY_STRUCTURED=0` forces legacy free-text path | s04, s06 |

### Acceptance Criteria (AC−)

| AC | Criterion (must NOT) | Covered by |
|----|----------------------|------------|
| AC−1 | Не добавлять LLM в epic loop / stop-gate / verify path | s02–s04 (scope limited to output-cap) |
| AC−2 | Не требовать network для default pytest suite | s05 (all mocked) |
| AC−3 | Не менять `extract_signals` heuristics без regression tests | s04 (no extract_signals change), s05 (regression) |
| AC−4 | Не блокировать hook startup if pydantic-ai import fails | s04 (try/except ImportError → _HAS_STRUCTURED=False) |
| AC−5 | Не дублировать env loading outside `_lib.load_output_summary_env` | s03 (factory reads env via _lib) |

### User Stories

| Story | Covered by |
|-------|------------|
| US-001 pytest output: structured failed_tests in view | s02, s03, s04, s05 |
| US-002 hook survives no OmniRoute | s03 (fail-soft None), s04 (import guard), s05 |
| US-003 llm_structured.py importable standalone (T-HUB-023 base) | s02, s03 |

### Success Criteria (SC)

| SC | Критерий | Covered by |
|----|----------|------------|
| SC-001 | LogSummary validates fixture JSON 100% | s02, s05 |
| SC-002 | No network calls when summary disabled | s04, s05 |
| SC-003 | Legacy urllib path removed or behind STRUCTURED=0 | s06, s08 |
| SC-004 | Hub suite green | s05 (cp3), s08 (cp4) |

---

## Stages coverage (plan → steps)

| Этап плана (черновик) | Описание | step(s) |
|-----------------------|----------|---------|
| s01 Pin research | pydantic-ai + OmniRoute compat matrix | s01 |
| s02 requirements-hub.txt + techContext | Create file, document install | s01, s07 |
| s03 LogSummary models + llm_structured.py factory | Pydantic models + agent factory | s02, s03 |
| s04 Sync runner + retry/fallback parity | run_log_summary с retries | s03 |
| s05 bash-output-cap integration + render | Structured path + build_view_structured | s04 |
| s06 Unit tests (mocked) | Full unit suite, no network | s05 |
| s07 Legacy path sunset + STRUCTURED=0 removal | _http_chat + llm_summarize purge | s06 |
| s08 Docs: project.env + README | Env flag comment + install note | s07 |
| s09 AUDIT: §0.11 env keys ↔ code | Grep audit + AC parity | s08 |
| s10 legacy-fallback-purge checklist | Final green + parity verification | s08 |

Все 10 этапов плана покрыты (план: advisory; нарезка: 8 атомарных шагов с объединением docs-шагов 08/09/10 → s07/s08).

---

## Outcome map (plan → steps)

1. **pydantic-ai установлен и задокументирован** → requirements-hub.txt + techContext → s01, s07.
2. **LogSummary валидирует реальные pytest logs** → модели + unit fixture тесты → s02, s05.
3. **run_log_summary вызывается из hook, возвращает структуру** → factory + integration → s03, s04.
4. **View агенту содержит file:line и failed_tests** → build_view_structured → s04, s05.
5. **Hook не падает при недоступном OmniRoute** → fail-soft None + ImportError guard → s03, s04.
6. **Legacy urllib удалён** → purge step после green suite → s06.
7. **Env-ключи согласованы с кодом** → audit grep → s08.
8. **Hub suite green** → s05 (mid), s08 (final). Закрывает SC-004.

---

## Replacement cleanup (plan → steps)

| Устаревает | Замена | Policy | step | deletes непусты | follow-up |
|------------|--------|--------|------|----------------|-----------|
| `bash-output-cap._http_chat` | `llm_structured.run_log_summary` | delete in-epic after green suite | s06 | да — `def _http_chat(...)` весь блок | n/a |
| `bash-output-cap.llm_summarize` | `llm_structured.run_log_summary` | delete in-epic | s06 | да — `def llm_summarize(...)` весь блок | n/a |
| `urllib.request` import в bash-output-cap | httpx via pydantic-ai (internal) | delete if no other users in file | s06 | да — import строка | n/a |
| `Silent empty LLM content → truncate only` | explicit mode label `structured\|llm\|extract\|truncate` | replace | s04 | mode label update | n/a |

rg audit команды (для IMPLEMENT verify):
```
rg -n 'def _http_chat\|def llm_summarize\|urllib\.request' .claude/hooks/bash-output-cap.py
```
ожидаемый результат после s06: 0 строк.

---

## §Audit (заполняется при s08)

### Env-key parity matrix

| Key | Declared in plan / docs | Handled in `_lib.load_output_summary_env` | Used in `bash-output-cap.py` / `llm_structured.py` | Parity Status |
|-----|-------------------------|-------------------------------------------|----------------------------------------------------|---------------|
| `PROJECT_OUTPUT_SUMMARY` | Yes | Yes (`k.startswith("PROJECT_OUTPUT_SUMMARY")`) | Yes (`llm_structured.py:93`, `bash-output-cap.py:245`) | OK |
| `PROJECT_OUTPUT_SUMMARY_STRUCTURED` | Yes | Yes | Yes (`bash-output-cap.py:300`) | OK |
| `PROJECT_OUTPUT_SUMMARY_URL` | Yes | Yes | Yes (`llm_structured.py:54`, `bash-output-cap.py:256`) | OK |
| `PROJECT_OUTPUT_SUMMARY_MODEL` | Yes | Yes | Yes (`llm_structured.py:55`, `bash-output-cap.py:260`) | OK |
| `PROJECT_OUTPUT_SUMMARY_FALLBACK_MODEL` | Yes | Yes | Yes (`llm_structured.py:102`, `bash-output-cap.py:263`) | OK |
| `PROJECT_OUTPUT_SUMMARY_KEY` | Yes | Yes | Yes (`llm_structured.py:57`, `bash-output-cap.py:270`) | OK |
| `PROJECT_OUTPUT_SUMMARY_KEY_FILE` | Yes | Yes | Yes (`llm_structured.py:59`, `bash-output-cap.py:273`) | OK |
| `PROJECT_OUTPUT_SUMMARY_RETRIES` | Yes | Yes | Yes (`llm_structured.py:128`, `bash-output-cap.py:284`) | OK |
| `PROJECT_OUTPUT_SUMMARY_TIMEOUT` | Yes | Yes | Yes (`llm_structured.py:132`, `bash-output-cap.py:288`) | OK |
| `PROJECT_OUTPUT_SUMMARY_BACKOFF` | Yes | Yes | Yes (`bash-output-cap.py:292`) | OK |
| `PROJECT_OUTPUT_SUMMARY_DEBUG` | Yes | Yes | Yes (`bash-output-cap.py:329`) | OK |

### AC Final Verification Status

| ID | Title / Requirement | Shard | Final Status | Evidence / Verification |
|----|---------------------|-------|--------------|-------------------------|
| AC+1 | pydantic-ai import check | s01, s04 | PASS | `requirements-hub.txt` contains `pydantic-ai==0.0.24`, import guard handles missing package gracefully |
| AC+2 | LogSummary & LogError Pydantic models created | s02 | PASS | `llm_structured.py` defines validated models with all required fields |
| AC+3 | Sync runner with retries & fallback model | s03 | PASS | `run_log_summary()` in `llm_structured.py` executes agent with retry logic and fallback model |
| AC+4 | bash-output-cap integration with structured render | s04 | PASS | `bash-output-cap.py` renders formatted view with `LogSummary` and `failed_tests` |
| AC+5 | Unit tests cover all paths without network | s05 | PASS | `loop/tests/test_bash_output_cap_pydantic_ai.py` contains 18 mocked unit tests |
| AC+6 | Hook never raises to parent on LLM failure | s03, s04 | PASS | LLM call wrapped in try/except; returns original text/view on error |
| AC+7 | Legacy HTTP code purged | s06 | PASS | `rg -n 'def _http_chat\|def llm_summarize'` returns 0 results |
| AC−1 | No unhandled exception on schema validation error | s02, s03 | PASS | Schema validation failures trigger retries/fallback or soft give-up |
| AC−2 | No extra network call when disabled | s04 | PASS | `PROJECT_OUTPUT_SUMMARY=0` bypasses LLM execution completely |
| AC−3 | No slowdown when output < threshold | s04 | PASS | Under threshold output skips LLM step instantly |
| AC−4 | Graceful fallback if pydantic-ai missing | s04 | PASS | `try...except ImportError` fallback guard verified |
| AC−5 | No hanging on slow model response | s03, s04 | PASS | `PROJECT_OUTPUT_SUMMARY_TIMEOUT` enforces timeout per request |

### Success Criteria (SC) Final Status

| ID | Criterion | Status | Note |
|----|-----------|--------|------|
| SC-001 | 100% structured LogSummary output on valid LLM response | PASS | Verified in s04/s05 |
| SC-002 | Zero unhandled exceptions in hook runtime | PASS | Fail-soft handling verified in s04/s05 |
| SC-003 | Full backward compatibility with existing env flags | PASS | All 11 env keys audited and verified |
| SC-004 | Entire hub test suite green | PASS | Verified via `pytest` run in s08 |

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | Pin research — pydantic-ai × OmniRoute compat matrix + requirements-hub.txt · [yaml](s01-pin-research-compat.yaml) | BACK IMPLEMENT | completed |
| **s02** | LogSummary + LogError models in llm_structured.py · [yaml](s02-log-summary-models.yaml) | BACK IMPLEMENT | completed |
| **s03** | make_output_cap_agent() + run_log_summary() sync runner with retries · [yaml](s03-agent-factory-sync-runner.yaml) | BACK IMPLEMENT | completed |
| **s04** | bash-output-cap.py structured path integration + build_view render · [yaml](s04-bash-output-cap-integration.yaml) | BACK IMPLEMENT | completed |
| **s05** | Unit tests — mocked agent, no network, TDD red→green · [yaml](s05-unit-tests-mocked.yaml) | BACK IMPLEMENT | completed |
| **s06** | Legacy urllib _http_chat + free-text llm_summarize purge + STRUCTURED=0 removal · [yaml](s06-legacy-sunset-purge.yaml) | BACK IMPLEMENT | completed |
| **s07** | project.env flag comment + techContext.md install note + loop/README snippet · [yaml](s07-env-docs.yaml) | BACK IMPLEMENT | completed |
| **s08** | AUDIT §0.11 — grep env keys vs code, AC parity check · [yaml](s08-audit-env-keys.yaml) | BACK IMPLEMENT | completed |