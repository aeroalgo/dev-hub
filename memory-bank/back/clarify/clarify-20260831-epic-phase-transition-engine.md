# clarify — epic-phase-transition-engine

**plan_id:** n/a → **T-HUB-029** (предложение при PLAN; merge T-HUB-028)  
**slug:** epic-phase-transition-engine  
**role:** back  
**date:** 2026-08-31  
**feature_description:** Единая система переходов: Transition Engine (`resolve_next` + `arm_phase` + `promote_if_ready`) + phase registry + verify-per-phase (ex T-HUB-028) + step sync + DAG adapter; full unification, phased slices, BACK/FRONT/INTEG parity.  
**status:** done

---

## Контекст и цель

- **Вход:** обсуждение 2026-08-31 — дрейф DECOMPOSE→IMPLEMENT без ANALYZE; три семейства переходов; предложение Transition Engine.
- **Refs:** T-HUB-020 resolver; T-HUB-028 phase-verify-agents (merge); `analyze_gate`; `promote_decompose_phase_if_ready`; `loop/WORKFLOW.md`.
- **Цель CLARIFY:** снять ambiguity до `BACK PLAN`.
- **Ограничения:** dev-hub; in-flight T-HUB-024 не блокировать (alias-period).

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Единственный контракт смены фазы/очереди в loop/hooks/board — любой entry point через resolver + arm/promote; merge verify registry (028) чтобы FINISH gates не жили отдельно. |
| **Premises** | P1: resolver обходится promote/legacy arm — **accepted**. P2: sNN queue отдельный контур — **rejected для v1** (Q1=D: входит в scope). P3: mega-epic без slices ломает in-flight — **rejected** (Q2=B). P4: 028 отдельно = двойной дрейф — **rejected** (Q3=A merge). P5: portal DAG ≠ epic graph но нужен adapter — **accepted** (Q4=B). |
| **Weakest link** | L4 scope + tri-role parity (Q5=B) при активном T-HUB-024 — требует жёсткого alias-delegate и slice boundaries в DECOMPOSE. |
| **Anti-scope** | Замена `reduce_epic_lifecycle` целиком; rewrite portal scheduler internals; product `$PROJECT_ROOT` rollout вне dev-hub в v1. |
| **Verdict** | `needs_user_Q` → resolved via Q1–Q5 |

Grill-Q: 1 (G3).

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | **Clear** | Full unification; phased slices; merge 028 |
| data | Partial | phase registry yaml schema — в PLAN |
| UX-API | Partial | unified arm/promote response contract — в PLAN |
| NFR | **Clear** | alias-period; in-flight safe |
| integrations | **Clear** | roadmap, board, stop-gate, epic_resolve, DAG adapter |
| edge | Partial | plan-next override, stale analyze — gates in PLAN |
| constraints | **Clear** | Python loop + hooks; TDD; hub |
| terminology | **Clear** | Transition Engine; phase registry; supersede T-HUB-028 |

---

## Q→A log

### Q1 (Grill G3 — scope slice)
- **Question:** Какой минимальный shippable slice Transition Engine входит в первый PLAN-эпик?
- **Why it matters:** Размер эпика и связь с T-HUB-028.
- **Recommended:** Option A.
- **Answer:** **D** — Full unification: фазы + sync_cursor/sNN + DAG в одном эпике.
- **resolution:** resolved

### Q2 (delivery — mega-epic phasing)
- **Question:** Как доставлять D без блокировки in-flight эпиков?
- **Why it matters:** L4 без rollout = HALT risk.
- **Recommended:** Option B.
- **Answer:** **B** — один эпик, phased vertical slices + alias-delegate до sunset.
- **resolution:** resolved

### Q3 (T-HUB-028 coupling)
- **Question:** Как связать с T-HUB-028 phase-verify-agents?
- **Why it matters:** Registry + verify — один контракт.
- **Recommended:** Option A.
- **Answer:** **A** — Merge в один эпик; T-HUB-028 superseded.
- **resolution:** resolved

### Q4 (DAG scope)
- **Question:** Что входит в «DAG»?
- **Why it matters:** portal DAG ≠ epic graph.
- **Recommended:** Option B.
- **Answer:** **B** — Epic graph + DAG adapter; scheduler unchanged.
- **resolution:** resolved

### Q5 (role parity)
- **Question:** Какие роли в v1?
- **Why it matters:** Scope тестов и sunset.
- **Recommended:** Option A.
- **Answer:** **B** — BACK + FRONT + INTEG полный parity в одном эпике.
- **resolution:** resolved

---

## Deferred / [НУЖНО УТОЧНИТЬ] items

| Item | Severity | Why deferred | Next |
|------|----------|--------------|------|
| Epic ID T-HUB-029 vs renumber | IMPORTANT | naming в PLAN | PLAN FINISH |
| phase registry yaml schema | IMPORTANT | детализация в PLAN §architecture | PLAN |
| Alias sunset timeline (N releases?) | NICE | DECOMPOSE slice | PLAN |
| CREATIVE per-step в registry | NICE | optional gate | PLAN defer |

Нет открытых **CRITICAL** blockers.

---

## Completion Report

- **Grill:** done · verdict=needs_user_Q → resolved · grill_Q=1
- **Asked:** 5/5
- **Resolved:** scope=D full unification; delivery=B phased slices+alias; 028 merge=A; DAG=B adapter; roles=B tri-role parity
- **Deferred:** epic id naming, registry schema detail, alias timeline, CREATIVE registry (IMPORTANT/NICE)
- **Coverage:** scope=Clear · data=Partial · UX-API=Partial · NFR=Clear · integrations=Clear · edge=Partial · constraints=Clear · terminology=Clear
- **Next action:** `BACK PLAN epic-phase-transition-engine` (предложить T-HUB-029, supersede T-HUB-028 в tasks/roadmap)
