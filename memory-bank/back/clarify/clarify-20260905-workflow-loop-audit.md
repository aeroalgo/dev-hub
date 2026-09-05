# clarify — workflow-loop-20260905

**plan_id:** T-HUB-062…069  
**slug:** workflow-loop-20260905  
**role:** back  
**date:** 2026-09-05  
**feature_description:** Из аудита `memory-bank/audit/workflow-loop-20260905` нарезать N BACK-эпиков, которые закрывают ложные green paths (skills, sunset boundary, video routes, duplicate hooks, schema/ownership, pack doctor, transactional finish, Codex policy).  
**status:** done

---

## Контекст и цель

- Вход: полный аудит `memory-bank/audit/workflow-loop-20260905/{index,01–08}.md` (снимок 2026-09-05).
- Цель сессии CLARIFY: Phase 0 внутри BACK PLAN; снять ambiguity нарезки эпиков и границ относительно уже существующих T-HUB-039/040/051/053/057/058/060/061.
- Ограничения: не трогать armed IMPLEMENT T-HUB-060; не один mega-plan; не создавать `plan/roadmap-*-epics.md`.

---

## Grill pass (Phase 0 — mandatory)

> Канон: @.agents/skills/grill-me/SKILL.md · shared-core §Phase 0

| Поле | Значение |
|------|----------|
| **Reframe** | Нужно превратить аудит в **исполняемые эпики**, которые закрывают ложный green (pack/route/schema/hooks), а не ещё один prose-отчёт. Сделано = старый обход нельзя использовать без ошибки. |
| **Premises** | 1. Аудит — SoT входа (accepted; Evidence: index.md + 01–08). 2. T-HUB-060 уже в IMPLEMENT s05 — не репланировать (accepted; Evidence: activeContext epic_id/step_id). 3. Дыры sunset/video/finish пересекаются с 058/051/040, но as-built 2026-09-05 всё ещё дырявый → новые leftover-эпики, не rewrite старых plan (accepted; Evidence: BOUNDARY_REGISTRY без sunset; manifest без video agents; settings.json dual hooks). 4. Queue.yaml сейчас `queue: []`, новые id идут в active queue (accepted; Evidence: roadmap/queue.yaml). 5. Codex TOML policy loss — отдельный риск от duplicate Claude hooks (accepted; Evidence: 01 §Codex materialization). |
| **Weakest link** | Склеить leftover в старые эпики 051/058/040 → DECOMPOSE возьмёт устаревший plan без audit evidence. |
| **Anti-scope** | Не завершать T-HUB-060; не чинить 15 падающих REFLECT-тестов этим PLAN; не MCP-only finish; не Cursor IDE Codex; не silent fallback на dual skill path. |
| **Verdict** | `auto_resolved` |

Evidence на premises: audit index P0/P1 tables; `loop/schemas/boundary_registry.py` 4 schemas; `harness/manifest.yaml` 8 agents; `.claude/settings.json` dual SessionStart; `memory-bank/back/roadmap/queue.yaml` `queue: []`; activeContext T-HUB-060 s05.

Grill-Q = 0.

---

## Product probe (office-hours lite)

| # | Вопрос | Контекст / Ответ |
|---|--------|------------------|
| 1 | **Demand reality** | Аудит 2026-09-05: pack ok при missing workflow; sunset JSON не в registry; Claude hooks ×2; skills `@` path 404. |
| 2 | **Status quo** | Operator/loop думает, что gate/pack/agent контракт enforced; фактически часть запретов — prose. |
| 3 | **Desperate specificity** | `full_resolve()` / parity checker / SubagentStop / SessionStart — ложный green. |
| 4 | **Narrowest wedge** | P0: skills topology + sunset stop + video routes/manifest. |
| 5 | **Observation & surprise** | Video pack резолвится; route_command строит несуществующие role-subdir. Sunset модель есть, registry нет. |
| 6 | **Future-fit** | Один Contract Registry (P2) обесценит точечные патчи, если не заложить fingerprint/SoT сейчас. |

- **Reframe:** закрыть false-green orchestration, не «добавить docs».
- **Premises (3–5 falsifiable):** см. Grill.
- **Recommended wedge:** 8 эпиков; первый DECOMPOSE = T-HUB-062.

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear | 8 эпиков по cut-критериям P0/P1 + деревья кода; T-HUB-060 out |
| data | Clear | machine JSON schemas, sidecars, queue.yaml, settings.json |
| UX-API | Clear | CLI doctor/validate-boundary/mb-finish/mb-load; нет UI |
| NFR | Clear | fail-closed, no silent fallback, idempotent stop, no duplicate hooks |
| integrations | Clear | Claude/Codex materialize, video pack, skill layout |
| edge | Clear | malformed pack yaml, no-fence verdict, partial load bundle, crash mid-finish |
| constraints | Clear | brownfield replace; не ломать armed 060; yaml-only roadmap |
| terminology | Clear | schema ids, verify_agent, realpath duplicate, usable pack |

Критичных ambiguity нет.

---

## Epic cut (MULTI-EPIC PLAN — 8)

| ID | slug | leftover vs | level | hard deps |
|----|------|-------------|-------|-----------|
| T-HUB-062 | skill-topology-canonical-paths | P0.2 skills `@` | L3 | — |
| T-HUB-063 | sunset-boundary-stop-pipeline | P0.3 registry+stop (058 leftover) | L3 | — |
| T-HUB-064 | video-pack-route-verify-parity | P0.4 routes+manifest (051 leftover) | L3–L4 | — |
| T-HUB-065 | duplicate-hooks-runtime-entrypoint | P1.3+P1.4 dual hooks + inject runtime | L3 | — |
| T-HUB-066 | boundary-schema-ownership-strict | P1.1+P1.2 fence/schema + ownership | L3–L4 | T-HUB-063 |
| T-HUB-067 | pack-doctor-executable-graph | P1.5+P1.6 doctor graph + load bundle | L3–L4 | T-HUB-062, T-HUB-064 |
| T-HUB-068 | start-finish-transaction-boundary | P1 finish_handoff + crash window (040 leftover) | L3–L4 | T-HUB-066 |
| T-HUB-069 | agent-contract-registry-codex-policy | P0 Codex TOML policy + contract matrix | L3–L4 | T-HUB-064 |

T-HUB-060 REFLECT — **out of batch** (IMPLEMENT s05).

Queue order: 062 → 063 → 064 → 065 → 066 → 067 → 068 → 069.

---

## Q→A log

Критических ambiguity не найдено — grill-Q и taxonomy Q не задавались.

---

## Deferred / [НУЖНО УТОЧНИТЬ] items

| Item | Severity | Why deferred | Next |
|------|----------|--------------|------|
| P2 generated README / alias dedupe | NICE | не false-green | внутри T-HUB-069 hygiene или later |
| Полный ContextBoundaryService rewrite | IMPORTANT | 068 закрывает transaction/recovery; полный сервис-слой — cut_list | T-HUB-068 Appetite cut_list |

CRITICAL без resolve: нет.

---

## Completion Report

- **Grill:** done · verdict=auto_resolved · grill_Q=0
- **Asked:** 0/5
- **Resolved:** нарезка 8 эпиков; 060 out; leftover vs 040/051/058
- **Deferred:** P2 README; mega TransitionService (cut_list 068)
- **Coverage:** scope=Clear · data=Clear · UX-API=Clear · NFR=Clear · integrations=Clear · edge=Clear · constraints=Clear · terminology=Clear
- **Next action:** `BACK DECOMPOSE T-HUB-062` (new chat) · queue[0] `workflow-loop-20260905`

---

## PLAN FINISH (2026-09-05) — activeContext locked

Live loop owns `memory-bank/activeContext.md` (`T-HUB-060-remove-reflect-phase` IMPLEMENT s05, pid=3930358). PLAN не перезаписывал курсор.

**Intended load_now (после 060 или в чате DECOMPOSE 062):**

1. `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`
2. `memory-bank/back/roadmap/queue.yaml`
3. `memory-bank/back/plan/T-HUB-062-skill-topology-canonical-paths/md/plan.md`

**Intended Handoff:** BACK DECOMPOSE `T-HUB-062-skill-topology-canonical-paths`. **FORBIDDEN** next = ROADMAP MERGE. `code_changed: no`. T-HUB-060 не completed этим PLAN.
