# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-023-hooks-llm-fallbacks
**План:** [plan-T-HUB-023-hooks-llm-fallbacks.md](../plan-T-HUB-023-hooks-llm-fallbacks.md)
**Machine index:** [index.yaml](index.yaml) — **канон status**
**Дата:** 2026-08-31
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача (один prod-модуль или один test-file). Shard: `sNN-<slug>.yaml`.

> **DECOMPOSE-only:** coverage-таблицы ниже — доказательство нарезки. **IMPLEMENT `load_now` = work shard + `index.yaml`.** Этот файл в IMPLEMENT не грузить.
> **status SoT = `index.yaml` only.**

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность (сессия DECOMPOSE) |
| `architecture-patterns` | trigger-order, fail-soft hooks (сессия PLAN) |

**Per-step:** skills gate в каждом `sNN` (Core + situational из `skills-gate-situational.mdc`).

---

## Requirements coverage (plan → steps)

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| US-001 | Opt-in восстановление Handoff из кривого markdown | s04, s08 | wire + golden fixture |
| US-002 | Verdict fallback из transcript tail | s05, s08 | regex miss + flag on |
| US-003 | Default-off — CI/air-gapped без сети | s01, s08, s10 | env default 0 + mock call count |
| US-004 | Счётчик fallback в state/status | s07, s08 | `llm_fallback_used` counter |
| FR-001 | `run_handoff_extract`, `run_verdict_extract`, `run_abort_classify` | s02, s03 | models + runners |
| FR-002 | `extract_handoff_block_llm_fallback` после regex miss | s04 | централизованно в extract chain |
| FR-003 | `extract_verdict` regex first; LLM tail opt-in | s05 | verify/reviewer agent_type gate |
| FR-004 | `classify_abort` optional LLM | s06 | inconclusive regex only |
| FR-005 | `load_hooks_llm_env()` single place | s01 | `_lib.py` |
| FR-006 | try/except fail-soft; `PROJECT_HOOKS_LLM_DEBUG` | s03, s04, s05, s06 | never crash hook |
| FR-007 | Confidence threshold ≥0.7 configurable | s02, s03, s04, s05, s06 | apply gate |
| FR-008 | Mock pydantic-ai Agent; anonymized fixtures | s08 | `test_hooks_llm_fallback.py` |
| FR-009 | Document flags in project.env + loop/README | s09 | § reliability |
| FR-010 | No fallback when regex succeeded | s05, s10 | grep + test |
| SC-001 | Default off → 0 LLM calls in tests | s08, s10 | pytest mock |
| SC-002 | Handoff fallback ≥1 golden malformed | s08 | pytest |
| SC-003 | Verdict fallback buried PASS | s08 | pytest |
| SC-004 | No regression flags off vs baseline | s08, s10 | full subset green |
| AC+ #1 | All flags default `0` in project.env template | s01, s09 | |
| AC+ #2 | Regex happy path byte-stable | s04, s05, s10 | golden unchanged |
| AC+ #3 | Three structured models + runners | s02, s03 | |
| AC+ #4 | Confidence gate enforced | s03, s08 | |
| AC+ #5 | `llm_fallback_used` incremented on apply | s07, s08 | |
| AC+ #6 | Mocked unit tests each domain | s08 | |
| AC+ #7 | README when to enable | s09 | |
| AC− #1 | Не default-on | s01, s09 | |
| AC− #2 | Не LLM на каждый check_after/stop-gate | s04, s05, s06 | only on primary miss |
| AC− #3 | Не заменять spawn-hard VERDICT protocol | s05, s09 | docs explicit |
| AC− #4 | Не блокировать session if LLM unavailable | s03, s06 | fail-soft |
| AC− #5 | Не fallback below MIN_CHARS (200) | s01, s03, s08 | |
| AC− #6 | Не дублировать OmniRoute config | s01, s03 | reuse 021 URL/key |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Env contract + master/per-domain flags | plan §s01, FR-005 | s01 |
| Pydantic extract models (Handoff/Verdict/Abort) | plan §s02, FR-001 | s02 |
| LLM runners в `llm_structured.py` | plan §s03, FR-001, FR-006, FR-007 | s03 |
| Handoff wire-in `epic/core.py` | plan §s04, FR-002, trigger order | s04 |
| Verdict wire-in `_lib.py` | plan §s05, FR-003, FR-010 | s05 |
| Abort wire-in `session_resilience.py` | plan §s06, FR-004 | s06 |
| Drift counter + status exposure | plan §s07, US-004, AC+5 | s07 |
| Fixtures + mocked domain tests | plan §s08, FR-008, TDD plan | s08 |
| Docs project.env + loop/README | plan §s09, FR-009 | s09 |
| AUDIT happy-path zero-call proof | plan §s10, FR-010, SC-001/004 | s10 |
| Trigger order: typed/sidecar → regex → LLM | plan §Зафиксированные решения | s04, s05, s06, s10 |
| TDD: `test_extract_verdict_regex_only_no_llm` | plan §TDD plan #1 | s08, s10 |
| TDD: handoff/verdict/abort fallback cases | plan §TDD plan #2–4 | s08 |
| TDD: full agent_hooks regression flags off | plan §TDD plan #5 | s10 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Снизить fingerprint_stall / verify_no_verdict через редкий structured LLM fallback | s04, s05, s08 |
| Default-off: zero network в CI/air-gapped (US-003, AC−1) | s01, s08, s10 |
| Happy path: zero LLM calls когда regex succeeds (AC+2, FR-010) | s04, s05, s10 |
| Observability: drift counter при успешном fallback (US-004) | s07, s08 |
| Trigger order never skip typed/regex (plan §Trigger order) | s04, s05, s06 |
| Confidence gate отсекает низкое качество LLM (FR-007) | s02, s03, s08 |
| Fail-soft: hook never crashes on LLM error (AC−4, FR-006) | s03, s04, s05, s06 |
| Soft clarification: LLM только в `extract_handoff_block` chain, не inline `repair_fingerprint_stall` | s04 |
| Out of scope: замена spawn-hard prompts | — | docs s09 |
| Out of scope: default-on fallback | — | s01 env |
| Deps: T-HUB-021 `llm_structured` client (hard) | s03 consumes |
| Deps: T-HUB-022 `DriftCounters`, typed path (soft) | s07 |

---

## Replacement cleanup (plan → steps)

| Устаревает (path / symbol) | Kind (A\|B\|C) | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| n/a — нет замен | — | — | — | — | greenfield additive; plan §Replacement A/B = n/a |
| Immediate NEED_HUMAN on regex miss (operational pain) | C | optional LLM recovery before NEED_HUMAN | — | yes | keep both paths; LLM opt-in only — не deletes |

---

## Очередь шагов (BACK)

| step_id | title & files | implement | needs_creative | tdd | next_phase | status |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-hooks-llm-env.yaml](s01-hooks-llm-env.yaml) | [s01…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s01-hooks-llm-env.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s02** | [s02-extract-models.yaml](s02-extract-models.yaml) | [s02…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s02-extract-models.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s03** | [s03-llm-runners.yaml](s03-llm-runners.yaml) | [s03…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s03-llm-runners.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s04** | [s04-handoff-wire.yaml](s04-handoff-wire.yaml) | [s04…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s04-handoff-wire.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s05** | [s05-verdict-wire.yaml](s05-verdict-wire.yaml) | [s05…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s05-verdict-wire.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s06** | [s06-abort-wire.yaml](s06-abort-wire.yaml) | [s06…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s06-abort-wire.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s07** | [s07-fallback-counter.yaml](s07-fallback-counter.yaml) | [s07…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s07-fallback-counter.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s08** | [s08-fallback-tests.yaml](s08-fallback-tests.yaml) | [s08…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s08-fallback-tests.yaml) | no | yes | BACK IMPLEMENT | pending |
| **s09** | [s09-docs-env-readme.yaml](s09-docs-env-readme.yaml) | [s09…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s09-docs-env-readme.yaml) | no | no | BACK IMPLEMENT | pending |
| **s10** | [s10-audit-zero-llm.yaml](s10-audit-zero-llm.yaml) | [s10…](../../implement/implement-T-HUB-023-hooks-llm-fallbacks/s10-audit-zero-llm.yaml) | no | yes | BACK IMPLEMENT | pending |
