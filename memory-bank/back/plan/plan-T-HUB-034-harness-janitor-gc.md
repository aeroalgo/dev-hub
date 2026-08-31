# [T-HUB-034 | harness-janitor-gc] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-026 (reconcile parsers).

**Skills:** writing-plans · python-testing-patterns · architecture-patterns

→ [decompose-T-HUB-034-harness-janitor-gc/index.md](decompose-T-HUB-034-harness-janitor-gc/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** OpenAI harness **doc gardening / garbage collection**: periodic scan for stale memory-bank artifacts, orphan implement yaml, dead plan refs, index mirror drift — automated report + optional bounded fixes (Tier-0 style).
- **gap:** reconcile-spec is on-demand; no scheduled/cron janitor; no GC for runtime episodes/incidents retention unified.
- **refs:** OpenAI harness engineering GC agent; T-HUB-026 reconcile; T-HUB-031 episode retention.

**CREATIVE need:** нет.

---

## Цель

CLI **`janitor-scan`** (read-only report) + optional **`janitor-gc`** (whitelist repairs only) для hub `$PROJECT_ROOT` — снижает entropy без full AUDIT.

---

## Продуктовая spека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator weekly, я хочу janitor report stale decompose indexes, чтобы entropy не копилась. | P0 | fixture orphan implement yaml → JN-001 |
| US-002 | Как platform, я хочу janitor-gc только whitelist paths, как tier0. | P0 | gc refuses product src/ |
| US-003 | Как operator, я хочу BACK JANITOR mode в router для guided run. | P1 | workflow-janitor.mdc read-only scan |

### Functional Requirements (FR-###)

- **FR-001:** Module `loop/janitor/` — `scan(cwd) -> JanitorReport` schema `janitor-report/v1`.
- **FR-002:** Finding categories: orphan_implement_yaml, stale_index_status, dead_plan_ref, duplicate_epic_id, orphan_events_dir, episode_retention_exceeded.
- **FR-003:** Reuse reconcile + traceability + index mirror checks.
- **FR-004:** CLI `epic_resolve.py janitor-scan` + `janitor-gc --dry-run|--apply` (apply = tier0-style repairs only: index mirror, prune episodes).
- **FR-005:** Workflow `.cursor/rules/back_developer/workflow-janitor.mdc` + lean gate (READ-ONLY scan path).
- **FR-006:** Register `BACK JANITOR` in mainrule (optional P1 if CLI sufficient v1).
- **FR-007:** Document weekly cron example in loop/README.md.
- **FR-008:** Tests per finding category; gc apply dry-run.

### Success Criteria

| SC-001 | Stale artifact detected | pytest fixture |
| SC-002 | gc apply refuses non-whitelist | pytest |
| SC-003 | janitor-report schema valid | pydantic test |

---

## AC

1. janitor-scan CLI + report schema.
2. janitor-gc dry-run/apply with whitelist.
3. Reuses reconcile parsers.
4. README cron doc.
5. Optional BACK JANITOR workflow.

---

## До DECOMPOSE

| sNN | Slice |
|-----|-------|
| s01 | janitor scan + schema |
| s02 | finding detectors |
| s03 | janitor-gc whitelist apply |
| s04 | CLI + tests |
| s05 | workflow + README |

---

## Следующий режим

→ BACK DECOMPOSE
