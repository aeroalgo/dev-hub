# [T-HUB-009 | dsh-rollout-docs] PLAN

**Дата:** 2026-08-22  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-dsh-loop-backend-epics.md](roadmap-dsh-loop-backend-epics.md)  
**Deps:** T-HUB-006, T-HUB-007, T-HUB-008

**Skills:** writing-plans

→ [decompose-T-HUB-009-dsh-rollout-docs/index.md](decompose-T-HUB-009-dsh-rollout-docs/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** документировать opt-in DSH backend, pilot runbook, architecture shard, зависимости; **не** включать DSH as default.
- **deps:** T-HUB-006…008 implemented.
- **refs:** `memory-bank/architecture/`, `loop/README.md`, `loop/WORKFLOW.md`, `README.md` (hub root), T-HUB-005 simplify-docs (may overlap — coordinate, don't duplicate cheatsheets).

### Зафиксированные решения

| Тема | Решение |
|------|---------|
| Default runtime | Document explicitly: **`EPIC_RUNTIME=claude`** |
| Pilot scope | One product repo (e.g. ai-server), one epic phase (IMPLEMENT), headless only |
| Architecture | New shard `memory-bank/architecture/dsh-runtime.md`; link from `index.md` |
| Runbook | `docs/runbooks/dsh-loop-pilot.md` in dev-hub |
| DSH stability | Banner: developer preview, pin version, breaking changes expected |
| Cursor | Document: Cursor chat remains Claude/rules path; DSH = loop headless only |
| Merge roadmap | After PLAN: `BACK ROADMAP MERGE` for slug queue |

**CREATIVE need:** нет.

---

## Цель

Разработчик может пройти pilot checklist и запустить `EPIC_RUNTIME=dsh make loop ARGS="…"` без устных инструкций; architecture честно описывает dual-runtime.

---

## Требования

### FR

| ID | Требование |
|----|------------|
| FR-1 | `docs/runbooks/dsh-loop-pilot.md`: prereqs, install, env, first run, troubleshooting |
| FR-2 | `memory-bank/architecture/dsh-runtime.md`: diagram loop+DSH layers, env table, failure modes |
| FR-3 | `memory-bank/architecture/index.md`: link dsh-runtime shard |
| FR-4 | `memory-bank/architecture/services.md`: DSH as optional session executor |
| FR-5 | `loop/README.md` + `WORKFLOW.md`: EPIC_RUNTIME section |
| FR-6 | Hub `README.md`: pointer to dsh/ + pilot runbook |
| FR-7 | Pilot checklist AC: 10 steps sign-off table |
| FR-8 | Explicit «not production default» statement in all entry docs |

### NFR

| ID | Требование |
|----|------------|
| NFR-1 | Docs match as-built after 006–008 (no aspirational APIs) |
| NFR-2 | Russian language for memory-bank docs (telegraph ok for non-plan) |
| NFR-3 | No duplicate of T-HUB-005 full cheatsheet — cross-link only |

### AC+

1. `test -f docs/runbooks/dsh-loop-pilot.md`  
2. `test -f memory-bank/architecture/dsh-runtime.md`  
3. architecture index links dsh-runtime  
4. Runbook includes: Node version, DSH pin, DEEPSEEK_API_KEY, install-profiles, EPIC_RUNTIME=dsh example  
5. Runbook troubleshooting: missing dsh, profile not found, gate deny, API 429  
6. Pilot checklist with sign-off row for verify gate parity  

### AC−

1. Не declare DSH production-ready  
2. Не remove Claude documentation  
3. Не auto-enable EPIC_RUNTIME in Makefile  

---

## Pilot checklist (content for runbook)

| # | Step | Pass criteria |
|---|------|---------------|
| 1 | Node 22+ installed | `node -v` |
| 2 | `npx @deepseek-ai/dsh --version` | exits 0 |
| 3 | API key in `$DSH_HOME/.credentials.yaml` | web or headless smoke |
| 4 | `dsh/scripts/install-profiles.sh` | profiles in DSH_HOME |
| 5 | `dsh/scripts/sync-agent-md-to-presets.py` | presets fresh |
| 6 | Product `hub-link` + `.dev-hub` | rules synced |
| 7 | `EPIC_RUNTIME=dsh bin/loop $PROJECT_ROOT decompose-… gpt` | session starts |
| 8 | IMPLEMENT step completes seed→verify→finalize | index completed |
| 9 | `EPIC_RUNTIME=claude` same epic step | no regression |
| 10 | Human sign-off | date + operator |

---

## Компоненты / файлы

| Файл | Действие |
|------|----------|
| `docs/runbooks/dsh-loop-pilot.md` | Create |
| `memory-bank/architecture/dsh-runtime.md` | Create |
| `memory-bank/architecture/index.md` | Update links |
| `memory-bank/architecture/services.md` | DSH paragraph |
| `memory-bank/architecture/data-flow.md` | Optional dual-runtime diagram |
| `loop/README.md` | EPIC_RUNTIME |
| `loop/WORKFLOW.md` | Runtime section |
| `README.md` | Hub pointer |
| `dsh/README.md` | Final polish cross-links |

---

## Replacement / sunset

n/a — documentation only.

---

## До DECOMPOSE (черновик фаз)

1. **s01 — architecture/dsh-runtime.md + index links**  
2. **s02 — runbook dsh-loop-pilot.md**  
3. **s03 — loop README/WORKFLOW + hub README**  
4. **s04 — services/data-flow touch-ups**  
5. **s05 — review vs as-built 006–008 (audit pass)**

---

## Следующий режим

→ **BACK DECOMPOSE T-HUB-009** (after T-HUB-008 QA)

После всей queue: optional **`BACK ROADMAP MERGE`** если slug ещё не в canon; pilot в product repo — human-driven outside loop.
