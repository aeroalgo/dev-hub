# clarify — dsh-full-purge

**plan_id:** n/a (Phase 0 of BACK PLAN)  
**slug:** dsh-full-purge  
**role:** back  
**date:** 2026-09-16  
**feature_description:** Полностью выпилить DSH из dev-hub: дерево `dsh/`, runtime adapter, registry/CLI/dispatch, тесты, instruction surfaces и docs, чтобы sole supported runtimes остались без DSH-пути.  
**status:** active

---

## Контекст и цель

- Вход: пользователь `BACK PLAN выпилить из проекта все что касается DSH полностью`
- Цель сессии CLARIFY: снять ambiguity scope/history/runtimes до Phase 1 plan (+ возможный multi-epic cut)
- Ограничения: текущий Handoff = BACK IMPLEMENT `T-HUB-104` s05 (не смешивать с PLAN-артефактами этого purge); historical DSH-эпики 006–020 уже в archive/done
- Spike? нет

### Inventory snapshot (sunset seed, live)

| Surface | Examples |
|---------|----------|
| Tree | `dsh/` (profiles, presets, plugins, patches, scripts, README) |
| Loop adapter | `loop/runtime_adapters/dsh.py` · registry · `EPIC_RUNTIME=dsh` · `runtime_sync` choices · `prompt_builder` · `epic_transition` · session events |
| Harness | `harness/hooks/_lib.py` (runtime set) · `harness/hooks/dsh_stream_filter.py` · manifest |
| Docs / Kind I | `DSH.md` · `AGENTS.md`/`CLAUDE.md` DSH branch · `LOOP-RUNTIMES.md` · `README.md` · runbooks · architecture `dsh-runtime.md` |
| Tests | `loop/tests/test_*dsh*` · registry/session/context_loop кейсы с `runtime="dsh"` |
| History (policy TBD) | `memory-bank/back/plan/T-HUB-00*-dsh-*` · archive roadmaps · events/qa artifacts |

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Не «почистить docs», а **закрыть DSH как machine runtime path**: после эпика(ов) нельзя выбрать/запустить/учить DSH без fail-closed; дерево и адаптер удалены, sole path = Claude Code + Codex (если подтвердят). |
| **Premises** | 1) DSH больше не нужен как supported runtime — `challenged` (нужен confirm). 2) «Полностью» = live code+tests+instruction surfaces, не обязательно rewrite всей history memory-bank — `challenged`. 3) После cutover `EPIC_RUNTIME=dsh` / `--runtime dsh` → явная ошибка, не silent fallback на claude — `accepted` (spec-first / AC−). 4) Объём ≥2 деревьев (`dsh/` TS + `loop/` Python + Kind I) → multi-epic cut вероятен — `deferred` до inventory в PLAN. 5) Исторические plan/QA артефакты про DSH можно оставить как archive text — `deferred` (Q1). |
| **Weakest link** | Что считать «полностью»: live sole-path vs scrub всех упоминаний в history memory-bank — от этого зависит L-level и multi-epic. |
| **Anti-scope (черновик)** | Не трогать Cursor/Codex/Claude Code adapters кроме удаления DSH-веток; не переписывать чужие done-эпики HOW; не начинать IMPLEMENT в этой сессии. |
| **Verdict** | `needs_user_Q` |

---

## Product probe (office-hours lite, optional)

| # | Вопрос | Контекст / Ответ |
|---|--------|------------------|
| 1 | **Demand reality** | Пользователь явно: выпилить DSH полностью. |
| 2 | **Status quo** | DSH opt-in (`EPIC_RUNTIME=dsh`), дерево `dsh/`, adapter в registry рядом с claude/codex. |
| 3 | **Desperate specificity** | Третий runtime + Kind I ветки в AGENTS/CLAUDE/DSH.md + install scripts = drift и поддержка. |
| 4 | **Narrowest wedge** | Loop sole-path deny `dsh` + delete adapter/tree + rewrite Kind I (один vertical slice / N эпиков с deps). |
| 5 | **Observation & surprise** | После T-HUB-086 Python supervisor DSH всё ещё first-class в registry/tests. |
| 6 | **Future-fit** | Если позже вернут DeepSeek-harness — отдельный greenfield epic, не shim. |

- **Reframe:** sole supported agent runtimes без DSH.
- **Premises:** см. Grill pass.
- **Recommended wedge:** live purge (code+tests+docs/rules), history memory-bank leave as-is unless Option B.

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Partial | «полностью» vs history vs live |
| data | Clear | нет новых сущностей; удаление runtime id |
| UX-API | Partial | CLI `--runtime` / env contract после purge |
| NFR | Partial | fail-closed vs fallback (policy clear, evidence TBD) |
| integrations | Partial | внешний `dsh` binary / DSH_HOME — удалить или deny |
| edge | Partial | misconfig `EPIC_RUNTIME=dsh` после cutover |
| constraints | Partial | очередь vs in-flight T-HUB-104 |
| terminology | Partial | запрет синонимов deepseek-harness / dsh в instruction |

Канон категорий: shared clarify-core §Таксономия.

---

## Q→A log

### Q1 (Grill G4 — scope boundary)
- **Question:** Что входит в «выпилить DSH полностью» по глубине истории?
- **Why it matters:** Меняет sunset inventory (A/B/C/I), multi-epic cut и AC− на `rg` hits в memory-bank.
- **Recommended:** Option A — live sole-path only.
- Options:

| Option | Description |
|--------|-------------|
| A | Live only: код (`dsh/`, adapters, registry, CLI), тесты на DSH-контракт, docs/runbooks/architecture Kind I, entrypoints. Historical `memory-bank/**/plan|qa|audit|events` про прошлые DSH-эпики **оставить** (archive text OK). |
| B | Live + scrub active memory-bank prose (architecture index, tasks.md rows, non-archive docs), но **не** переписывать archived epic trees / events payloads. |
| C | Maximal scrub: удалить/переписать **все** упоминания DSH включая historical plan/QA/events (дорого, high risk integrity). |

- **Answer:** _(ожидается)_
- **resolution:** pending

---

## Completion Report

_(после закрытия Q)_
