# clarify — plan-refactor

**plan_id:** n/a (нарезка после Phase 1)  
**slug:** plan-refactor  
**role:** back  
**date:** 2026-09-12  
**feature_description:** Deletion- и consolidation-oriented BACK PLAN REFACTOR: evidence-backed scan → epic cut → queue/plan/prompt без смены поведения.  
**status:** active

---

## Контекст и цель

- Вход: команда `BACK PLAN REFACTOR` без path/package/theme; Handoff после EPIC_DONE T-HUB-090; в queue активны cadence T-HUB-092…094 и legacy row `plan`/T-HUB-076.
- Цель сессии CLARIFY: зафиксировать **scan scope**, exclusions, отношение к dirty working tree и к уже стоящим queue rows — иначе inventory/plans запрещены.
- Ограничения: planning-only (код/тесты не трогать); behavior freeze; net LOC/owners ≤ 0; не smuggle feature/bugfix.

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Нужен не «рефакторинг вообще», а bounded purge+consolidate план: что удалить/слить с proof, один owner на meaning cluster, без dual-path и без роста abstractions. |
| **Premises** | (1) Scope не задан командой → нельзя честно inventory весь репо без явного выбора · `challenged`. (2) После T-HUB-087…090 возможны leftover twins/shims в `loop/`+`harness/` · `deferred` до scan. (3) Dirty WT — baseline snapshot, не часть refactor delta · `accepted`. (4) Cadence T-HUB-093 = executor arm PLAN REFACTOR, не сам scan scope этой сессии · `accepted`. (5) Full-tree scan без явного запроса даёт поверхностный purge-only · `accepted`. |
| **Weakest link** | Без объявленного scope любой epic cut будет либо mega-cleanup, либо угадыванием — FAIL gates. |
| **Anti-scope** | Смена поведения/API; правка prod/test в PLAN; «layer move» без merge/delete; standalone test-cleanup без production twin; silent wrap legacy. |
| **Verdict** | `needs_user_Q` |

Grill-Q → Q1 (scan scope).

---

## Product probe (office-hours lite)

| # | Вопрос | Контекст / Ответ |
|---|--------|------------------|
| 1 | **Demand reality** | Команда роли после серии fallback-purge; отдельного brief нет. |
| 2 | **Status quo** | Двойные owners/shims ищут ad-hoc grep между эпиками. |
| 3 | **Desperate specificity** | Неясный scope → либо весь репо, либо пропуск consolidation. |
| 4 | **Narrowest wedge** | Один package/theme с twin clusters + deletion ledger. |
| 5 | **Observation & surprise** | Queue уже содержит cadence/feature rows — refactor epics встанут рядом/в голову по reconcile. |
| 6 | **Future-fit** | Cadence 093 позже авто-arm'ит PLAN REFACTOR — этот ручной проход должен иметь явный theme, чтобы не дублировать noop. |

- **Reframe:** bounded consolidate+purge plan, не feature epic.
- **Premises:** scope must be chosen; behavior freeze; graph available under `graphify-out/`.
- **Recommended wedge:** post-purge leftovers в `loop/` (+ связанные harness callers только как consumers того же meaning).

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Missing | path/package/theme не заданы — CRITICAL |
| data | Clear | нет новой persistence; SoT = code + tests + queue |
| UX-API | Clear | CLI/API behavior freeze; не меняем контракты |
| NFR | Partial | fail-closed / sole path — из behavior-first; latency out |
| integrations | Partial | graphify graph есть; runtime adapters — только если в scope |
| edge | Partial | dynamic import/config risk в dead-code proof |
| constraints | Partial | dirty WT freeze; queue already non-empty |
| terminology | Clear | purge / consolidate / cluster_id / canonical_owner / copies_removed_count |

---

## Q→A log

### Q1
- **Question:** Какой **scan scope** для этого BACK PLAN REFACTOR (path / package / theme)?
- **Why it matters:** Без scope нельзя строить baseline, twin clusters и epic cut; full-tree без явного запроса запрещён как default.
- **Recommended:** Option B — theme `post-087-090 leftover dual-path / shim / twin owners` в деревьях `loop/` + необходимые consumers в `harness/hooks/` (не весь harness).
- **Options:**
  | Option | Description |
  |--------|-------------|
  | A | Только `loop/` (package) |
  | B | Theme leftover dual-path/shim после 087–090: `loop/` + точечные `harness/hooks` consumers того же meaning |
  | C | Только `harness/hooks/` |
  | D | Другой явный path/package/theme (ответь ≤1 строкой) |
  | E | Full-tree (явно весь репозиторий; глубина consolidation ниже) |
- **Answer:** *(ожидается)*
- **resolution:** pending

---

## Deferred / [НУЖНО УТОЧНИТЬ] items

| Item | Severity | Why deferred | Next |
|------|----------|--------------|------|
| `[НУЖНО УТОЧНИТЬ: CRITICAL scan scope path/package/theme]` | CRITICAL | нет ответа Q1 | Q1 this session |
| Отношение новых refactor epics к head queue (076 / 092…) | IMPORTANT | после scope | Q2 если material |
| Exclusions generated/vendor/`memory-bank` artifacts | NICE | default exclude; уточнить при need | PLAN baseline |

---

## Completion Report

- **Grill:** done · verdict=needs_user_Q · grill_Q=1 (in flight)
- **Asked:** 1/5 (awaiting A)
- **Resolved:** —
- **Deferred:** CRITICAL scope до ответа Q1
- **Coverage:** scope=Missing · data=Clear · UX-API=Clear · NFR=Partial · integrations=Partial · edge=Partial · constraints=Partial · terminology=Clear
- **Next action:** await Q1 → continue Phase 0 / then Phase 1 Plan writing
