# clarify — dsh-full-purge

**plan_id:** T-HUB-106-dsh-runtime-full-purge  
**slug:** dsh-full-purge  
**role:** back  
**date:** 2026-09-16  
**feature_description:** Удалить DSH runtime/implementation/libraries/tests и связанные live instruction surfaces; historical memory-bank epic trees не трогать.  
**status:** done

---

## Контекст и цель

- Вход: `BACK PLAN выпилить из проекта все что касается DSH полностью`
- User override (после Q1/Q2): **код/рантайм/библиотеки/тесты/docs-entrypoint** — удалить; **эпики memory-bank** — не трогать
- Spike? нет

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Закрыть DSH как machine runtime path: sole supported = Claude Code + Codex; дерево `dsh/`, adapter, registry/CLI и DSH-тесты удалены; misconfig `dsh` fail-closed. |
| **Premises** | 1) DSH не нужен как supported runtime — `accepted` (user). 2) Maximal history scrub **отменён** — `rejected` (user override: эпики не трогать). 3) `EPIC_RUNTIME=dsh` / `--runtime dsh` / `bin/loop dsh` → ошибка, не fallback — `accepted`. 4) Kind I live docs (DSH.md, runbooks, AGENTS/CLAUDE ветки) ∈ purge — `accepted` («вся хуйня» с реализацией). 5) Historical `memory-bank/**/plan|qa|audit|events` DSH-эпиков — `keep` out-of-scope — `accepted`. |
| **Weakest link** | Скрытый dual-path (silent fallback dsh→claude) при удалении только дерева. |
| **Anti-scope** | Не rewrite/delete historical epic trees; не трогать Claude/Codex adapters кроме удаления DSH-веток; не IMPLEMENT в PLAN. |
| **Verdict** | `auto_resolved` после user override (Evidence: chat Q1→C затем override «эпики не трогать / удалить весь код») |

---

## Product probe

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Demand reality | User: выпилить DSH реализацию и рантайм |
| 2 | Status quo | Opt-in `EPIC_RUNTIME=dsh` + дерево `dsh/` + adapter в registry |
| 3 | Desperate specificity | Третий runtime + libs/plugins + тесты = поддержка |
| 4 | Narrowest wedge | Registry deny + delete adapter/tree + delete DSH tests + Kind I rewrite |
| 5 | Observation | После supervisor cutover DSH всё ещё first-class |
| 6 | Future-fit | Новый harness = greenfield epic, не shim |

- **Recommended wedge:** live code+runtime+libs+tests+Kind I; history epics untouched.

---

## Таксономия сканирования (финал)

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear | live purge; history epics out |
| data | Clear | drop runtime id `dsh` |
| UX-API | Clear | CLI/env deny `dsh` |
| NFR | Clear | fail-closed |
| integrations | Clear | no external dsh binary wiring |
| edge | Clear | unknown runtime → error |
| constraints | Clear | queue after current; single epic |
| terminology | Clear | forbid teaching dsh as live runtime |

---

## Q→A log

### Q1
- **Question:** Глубина «полностью» (history)?
- **Answer:** C (maximal scrub) — **superseded** user override.
- **resolution:** superseded

### Q2 / Q2b
- **Question:** HOW history scrub?
- **Answer:** User override: **эпики не трогать**; удалить код/рантайм/библиотеки/тесты/связанную live-хуйню.
- **resolution:** resolved → policy **live-only purge** (≈ Q1-A по смыслу; history epic trees keep)

---

## Completion Report

```markdown
## Completion Report
- Grill: done (override after Q1/Q2)
- Taxonomy: all Clear for PLAN
- Q asked: 2 (+1 disambiguation) / 5
- CRITICAL open: 0
- Ready for Phase 1 PLAN: yes
- Outcome prompt Chat decisions: live purge only; history epics untouched; sole runtimes claude+codex
```
