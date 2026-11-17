# clarify — runtime-hub

**plan_id:** T-HUB-109-runtime-hub  
**slug:** runtime-hub  
**role:** back  
**date:** 2026-11-06  
**feature_description:** Runtime Hub в dev-hub — CLI-оркестратор официальных runtimes (Codex / Claude Code / Antigravity): isolated profiles, model, spawn native binary; OmniRoute только explicit profile; loop/UI later.  
**status:** done

---

## Контекст и цель

- Вход: чат 2026-11-06.
- Settled Round 1: Q1=A CLI-only · Q2=B Codex+Claude+agy · Q3=A isolated dirs · Q4=B loop later.
- Settled Round 2: Q5=B native Codex default, OmniRoute explicit · Q6=A agy spawn-only · Q7=A `~/.dev-hub/runtime-hub/` · Q8=A fail-closed.
- Deferred from MVP 109: loop SoT wire; agy HTTP-bridge; OmniRoute full deprecate; standalone Tauri/Electron IDE.
- **Post-plan intent (2026-11-06):** целевое приложение — **Cursor extension** поверх Hub (multi-window = parallel projects; per-window account+model). SoT: `memory-bank/back/intent/intent-20261106-runtime-hub-cursor-extension.md`. Кандидат эпика T-HUB-110.

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Profile+runtime switcher: isolate home → spawn official `codex`/`claude`/`agy`; no OAuth spoof proxy. |
| **Premises** | 1–8 **accepted** (Rounds 1–2). |
| **Weakest link** | Accidental OmniRoute default или silent fallback на `~/.codex` ломает isolation — закрыто Q5=B + Q8=A. |
| **Anti-scope** | UI; Cursor extension; loop cutover; agy OpenAI-bridge; OAuth token replay; public gateway; tracked secrets; auto-migrate login between profiles. |
| **Verdict** | `auto_resolved` (Evidence = Q→A R1+R2) |
| **Design tree** | All MVP nodes settled → PLAN HOW. |

---

## Product probe

- **Recommended wedge:** `runtime_hub/` + `bin/hub-runtime`; 3 spawn adapters; profiles under `~/.dev-hub/runtime-hub/`; fail-closed; OmniRoute = named profile only.

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear | CLI; 3 runtimes; no UI; no loop SoT |
| data | Clear | `~/.dev-hub/runtime-hub/` + per-profile homes |
| UX-API | Clear | use/status/run/doctor/list |
| NFR | Clear | fail-closed; spawn-only; no secret in git |
| integrations | Clear | OmniRoute explicit; agy spawn-only; loop deferred |
| edge | Clear | missing binary / unknown profile / active conflict → error |
| constraints | Clear | official binaries only |
| terminology | Clear | profile = runtime + account home + model |
| design_skills | n/a | |

---

## Frontier rounds

### Round 1 — DONE
Q1=A · Q2=B · Q3=A · Q4=B

### Round 2 — DONE
Q5=B · Q6=A · Q7=A · Q8=A

Frontier empty — no Round 3.

---

## Q→A log

| # | Topic | A |
|---|-------|---|
| 1 | MVP wedge | A CLI-only |
| 2 | Runtimes | B Codex+Claude+agy |
| 3 | Accounts | A isolated dirs |
| 4 | Loop | B standalone first |
| 5 | OmniRoute | B native default; OmniRoute explicit profile/flag |
| 6 | agy depth | A spawn-only, no HTTP bridge |
| 7 | Layout | A `~/.dev-hub/runtime-hub/` |
| 8 | Errors | A fail-closed, no silent fallback |

---

## Completion Report

- **status:** done
- **Grill:** done · verdict=auto_resolved · rounds=2 · grill_Q=8 · mode=frontier
- **Ready for Phase 1 PLAN:** yes
- **design_pack:** n/a
