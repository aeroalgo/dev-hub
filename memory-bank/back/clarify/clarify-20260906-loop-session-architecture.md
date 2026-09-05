# clarify — loop-session-architecture-20260906

**plan_id:** T-HUB-070…074  
**slug:** loop-session-architecture-20260906  
**role:** back  
**date:** 2026-09-06  
**feature_description:** Из runtime-аудита сессий (`claude-sessions-20260905-last15.md`) и архитектурного разбора (`loop-session-architecture-20260905.md`) нарезать leftover-эпики **Variant A** (Policy Registry + thin adapters), которые закрывают ложные SoT на фазу: overlay vs registry, identity lock, lean ContextBundle, abort classifier, QA/BUGFIX lifecycle. Не rewrite T-HUB-062…069.  
**status:** done

---

## Контекст и цель

- **Вход:** `memory-bank/audit/claude-sessions-20260905-last15.md` + `memory-bank/audit/loop-session-architecture-20260905.md` (Variant A recommended). Пользователь: «BACK PLAN выбираем рекомендованную архитектуру. Нужно сделать что бы всё работало как нужно.»
- **Цель:** Phase 0 внутри BACK PLAN; снять ambiguity нарезки leftover поверх уже существующих T-HUB-062…069 / 057 / 060 / 065 / 068.
- **Ограничения:**
  - T-HUB-062 armed IMPLEMENT s02 — **не** репланировать, **не** Write decompose/index этого эпика.
  - Не mega-plan. Не `plan/roadmap-*-epics.md`.
  - Variant B (event-sourced) и Variant C (orchestrator command bus) — **Appetite cut**, не этот батч.
  - Duplicate hooks / EPIC_RUNTIME inject = T-HUB-065 (уже PLAN). Sunset registry+stop = T-HUB-063. Fence/ownership = T-HUB-066. Finish journal = T-HUB-068. Skills FS = T-HUB-062. Codex policy = T-HUB-069. Pack doctor = T-HUB-067.

---

## Grill pass (Phase 0 — mandatory)

> Канон: @.agents/skills/grill-me/SKILL.md · shared-core §Phase 0

| Поле | Значение |
|------|----------|
| **Reframe** | Нужно не «ещё один аудит», а **один PhasePolicy** как machine SoT: hooks/CLI/prompts **генерируются или читаются из registry**, identity сессии не врёт COMMAND, ContextBundle fail-closed, abort 401 не штормит, QA yaml не может быть stale fail при уходе эпика. Сделано = старый overlay/regex/inline-plan нельзя использовать без ошибки. |
| **Premises** | 1. Variant A — выбранный SoT (accepted; Evidence: user «выбираем рекомендованную архитектуру» + architecture §10 A). 2. T-HUB-062…069 закрывают *другую* полосу leftover (skills/sunset/video/hooks-dup/schema/doctor/tx/codex) — этот батч **не** rewrite их WHAT (accepted; Evidence: queue batch `workflow-loop-20260905` + architecture §9 rows 8–13 vs 1–7,18–19,24). 3. Overlay `user-prompt.py` всё ещё пишет REFLECT + DECOMPOSE verify OFF (accepted; Evidence: `harness/hooks/user-prompt.py` L156, L164–171; `phase_registry.yaml` QA next не REFLECT, DECOMPOSE `verify_agent: verify-decompose`). 4. `load_session` ставит `ok=True` после missing_file continue (accepted; Evidence: `loop/mb_load/session.py` L66–70, L97). 5. `_TRANSIENT_ABORT_PATTERNS` ловит любой `API Error:` включая 401 banned (accepted; Evidence: `session_resilience.py` L97–113). 6. Identity lock (COMMAND == armed_step, step≠unknown) **не** в 065 (065 = duplicate realpath + runtime entrypoint) (accepted; Evidence: T-HUB-065 plan FR-001…010). |
| **Weakest link** | Склеить identity+overlay+bundle+abort в один mega-эпик или в 065/068 → DECOMPOSE возьмёт чужой plan без session-audit evidence; либо оставить overlay «потому что projection_authoritative» — DECOMPOSE armed всё ещё override verify OFF. |
| **Anti-scope** | Не завершать T-HUB-062 IMPLEMENT; не ContractRegistry codegen всех docs (069 cut / P2); не Event Sourcing projector (Variant B); не Mediator Orchestrator.next() (Variant C); не MCP-only finish; не Cursor IDE; не silent skill dual-path (062). |
| **Verdict** | `auto_resolved` |

Evidence на premises: architecture §10 A + P0.1–P0.5, P1 abort; session audit §5–6, §11; `user-prompt.py`; `phase_registry.yaml` DECOMPOSE/QA; `session.py` ok_status; `session_resilience.py` `_TRANSIENT_ABORT_PATTERNS`; queue.yaml T-HUB-062…069; activeContext T-HUB-062 s02.

Grill-Q = 0.

---

## Product probe (office-hours lite)

| # | Вопрос | Контекст / Ответ |
|---|--------|------------------|
| 1 | **Demand reality** | 15 сессий: BUGFIX vs QA inject; DECOMPOSE verify OFF vs workflow ANALYZE; 8× 401 retry; plan.md inline; QA yaml fail + queue ушёл. |
| 2 | **Status quo** | Пять SoT (loop prompt, SessionStart, overlay, mdc, AC). Послушный агент выбирает случайно. |
| 3 | **Desperate specificity** | `user-prompt.py` armed_step=DECOMPOSE блок; `load_session` ok=true; `API Error:` catch-all; `finish_qa` не требует re-QA yaml pass перед epic leave. |
| 4 | **Narrowest wedge** | P0: overlay = registry (delete REFLECT + verify OFF); identity lock COMMAND; bundle ok=false + path-only md. |
| 5 | **Observation & surprise** | Даже при `projection_authoritative` DECOMPOSE блок **после** projection всё равно выключает verify. 065 чинит dual hooks, не этот override. |
| 6 | **Future-fit** | Variant B projector обесценит AC regex, если identity lock не стабилен сейчас — сначала A. |

- **Reframe:** один PhasePolicy + fail-closed start/abort/QA; не «добавить docs».
- **Premises:** см. Grill.
- **Recommended wedge:** 5 эпиков; первый DECOMPOSE этого батча = T-HUB-070 (после текущего queue head 062, deps не блокируют 070 от 062).

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear | 5 leftover эпиков по cut-критериям architecture §9 rows 1,5–11,18–20,24; 062–069 out |
| data | Clear | phase_registry.yaml, state.json, mb-load-result, last-session.json, qa-*.yaml |
| UX-API | Clear | SessionStart additionalContext, UserPromptSubmit overlay, mb-finish qa/bugfix, abort CLI |
| NFR | Clear | fail-closed, no silent ok, identity halt, 401 NEED_HUMAN, sole SoT |
| integrations | Clear | Claude SessionStart/UserPromptSubmit; loop context_loop; mb-finish |
| edge | Clear | missing load_now file; COMMAND mismatch; 401 banned; stale QA fail; DECOMPOSE overlay vs registry |
| constraints | Clear | brownfield replace overlay/regex; не ломать armed 062; yaml-only roadmap |
| terminology | Clear | PhasePolicy, ContextBundle, identity lock, NEED_HUMAN, dirty_files, qa_after_bugfix |

Критичных ambiguity нет.

---

## Epic cut (MULTI-EPIC PLAN — 5)

Критерии cut (любой → отдельный эпик): приоритет (P0≠P1), другое дерево кода, другой тип риска, hard-dep, independent deliverable.

| ID | slug | leftover vs | level | hard deps | cut why |
|----|------|-------------|-------|-----------|---------|
| T-HUB-070 | phase-policy-overlay-sole-sot | architecture P0.1+P0.5; session §6 overlay REFLECT + DECOMPOSE verify OFF | L3 | — | P0 overlay SoT; дерево `user-prompt.py` + `phase_registry` consume |
| T-HUB-071 | session-identity-lock | architecture P0.3; session §5 BUGFIX vs QA COMMAND | L3 | T-HUB-070 | identity бесполезен, если overlay всё ещё врёт next/gates |
| T-HUB-072 | context-bundle-fail-closed | architecture P0.4; session §3 inline plan + ok=true | L3 | T-HUB-071 | bundle читает identity; path-only после lock |
| T-HUB-073 | abort-classifier-dirty-halt | architecture P1 abort + dirty_files; session §11 401×8 | L3 | — | ops risk / resilience tree, independent of overlay |
| T-HUB-074 | qa-bugfix-lifecycle-rearm | architecture §6 QA tx + §8 QA/BUGFIX; T-HUB-060 leftover overlay/yaml | L3 | T-HUB-070 | finish_qa/bugfix lifecycle; hard 070 чтобы next(QA)≠REFLECT |

**Не отдельные эпики (в cut_list / already queued):**

| Тема | Куда |
|------|------|
| Duplicate SessionStart ×2 | T-HUB-065 |
| Skill nested path | T-HUB-062 (armed) |
| Sunset registry | T-HUB-063 |
| Fence / ownership | T-HUB-066 |
| Finish journal / finish_handoff | T-HUB-068 |
| Codex TOML policy | T-HUB-069 |
| Pack doctor | T-HUB-067 |
| Event sourcing / Mediator | Appetite cut (Variant B/C) |
| ContractRegistry codegen README | T-HUB-069 cut_list |

---

## Q→A log

Критических ambiguity не найдено. Grill-Q = 0. Taxonomy Q = 0.

---

## Deferred / [НУЖНО УТОЧНИТЬ] items

| Item | Severity | Why deferred | Next |
|------|----------|--------------|------|
| — | — | нет открытых CRITICAL | — |

---

## Completion Report

- **Grill:** done · verdict=auto_resolved · grill_Q=0
- **Asked:** 0/5
- **Resolved:** Variant A; 5 leftover epics; 062–069 untouched as WHAT
- **Deferred:** Variant B/C; ContractRegistry encyclopedia
- **Coverage:** scope=Clear · data=Clear · UX-API=Clear · NFR=Clear · integrations=Clear · edge=Clear · constraints=Clear · terminology=Clear
- **Next action:** Phase 1 written 2026-09-06 — 5 plans + queue batch `loop-session-architecture-20260906` upserted. Current armed IMPLEMENT remains T-HUB-062 (do not re-arm 070). First DECOMPOSE of this batch = T-HUB-070 after queue head 062–069 no longer block.
