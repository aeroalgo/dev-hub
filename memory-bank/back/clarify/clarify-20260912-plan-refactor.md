# clarify — plan-refactor

**plan_id:** n/a (нарезка после Phase 1)  
**slug:** plan-refactor  
**role:** back  
**date:** 2026-09-12  
**feature_description:** Deletion- и consolidation-oriented BACK PLAN REFACTOR: evidence-backed scan → epic cut → queue/plan/prompt без смены поведения.  
**status:** done

---

## Контекст и цель

- Вход: команда `BACK PLAN REFACTOR`; Handoff после EPIC_DONE T-HUB-090; на момент Completion Report `roadmap/queue.yaml` → `queue: []` (076/092–094 в done).
- Цель CLARIFY: scan scope + exclusions; достигнуто.
- Ограничения: planning-only; behavior freeze; net LOC/owners ≤ 0.

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Bounded purge+consolidate план: удалить/слить с proof, один owner на meaning cluster, без dual-path. |
| **Premises** | (1) Scope = Option B · `accepted` (Q1). (2) Leftover twins/shims после 087–090 в `loop/` + точечные `harness/hooks` · `accepted` (hypothesis → scan). (3) Dirty WT — baseline, не delta · `accepted`. (4) Cadence 093 ≠ этот scan · `accepted`. (5) Full-tree не default · `accepted`. |
| **Weakest link** | Было: отсутствие scope — снято Q1=B. |
| **Anti-scope** | Смена поведения; код в PLAN; layer-move без merge; test-only cleanup; wrap legacy. |
| **Verdict** | `needs_user_Q` → resolved after Q1 |

---

## Product probe

- **Reframe:** post-purge leftover dual-path/shim consolidate+purge.
- **Recommended wedge:** `loop/` + точечные `harness/hooks` consumers того же meaning.
- **Chat decisions:** Q1 → B.

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear | Option B — theme leftover dual-path/shim: `loop/` + точечные `harness/hooks` consumers |
| data | Clear | SoT = code + tests + queue |
| UX-API | Clear | behavior freeze |
| NFR | Clear | fail-closed / sole path; latency out |
| integrations | Clear | graphify-out; harness only as consumers of loop meanings |
| edge | Clear | dynamic import risk → proof method в inventory, не ambiguity |
| constraints | Clear | queue empty; exclude `memory-bank/`, generated, vendor, `__pycache__`, `.venv` |
| terminology | Clear | purge / consolidate / cluster_id / canonical_owner / copies_removed_count |

---

## Q→A log

### Q1
- **Question:** Какой **scan scope** для этого BACK PLAN REFACTOR (path / package / theme)?
- **Why it matters:** Без scope нельзя строить baseline, twin clusters и epic cut.
- **Recommended:** Option B
- **Answer:** B
- **resolution:** resolved

### Q2+
- Не задавались: queue head не material (`queue: []`); exclusions default accepted.

---

## Deferred / [НУЖНО УТОЧНИТЬ] items

| Item | Severity | Why deferred | Next |
|------|----------|--------------|------|
| — | — | нет открытых CRITICAL | — |

---

## Completion Report

- **Grill:** done · verdict=resolved_after_Q1 · grill_Q=1
- **Asked:** 1/5
- **Resolved:** scan scope = B (loop + точечные harness/hooks consumers leftover dual-path/shim после 087–090)
- **Deferred:** none critical
- **Coverage:** scope=Clear · data=Clear · UX-API=Clear · NFR=Clear · integrations=Clear · edge=Clear · constraints=Clear · terminology=Clear
- **Next action:** `BACK PLAN REFACTOR` Phase 1 Plan writing
