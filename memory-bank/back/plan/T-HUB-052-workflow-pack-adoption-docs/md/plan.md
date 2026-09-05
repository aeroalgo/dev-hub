# [T-HUB-052 | workflow-pack-adoption-docs] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L2–L3  
**Статус:** active  
**Roadmap:** [roadmap-workflow-pack-framework-epics.md](roadmap-workflow-pack-framework-epics.md)  
**Queue:** [roadmap-workflow-pack-framework-epics.queue.yaml](roadmap-workflow-pack-framework-epics.queue.yaml)  
**Deps:** **hard** T-HUB-051 (reference pack shipped). **Soft:** T-HUB-044 (doctor/docs pattern), T-HUB-046 (hub-link alongside install).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · modern-python

→ [T-HUB-052-workflow-pack-adoption-docs/md/decompose-index.md](T-HUB-052-workflow-pack-adoption-docs/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Framework без adoption path = dead code. Operator needs: IDEA PIPELINE routes intents to packs; doctor preflight checks pack resolve + rules + phase yaml; runbook «как подключить свой pipeline»; hub-link installs optional pack rules tree; loop `--workflow-pack` flag documented.
- **gap:** IDEA PIPELINE intent table — software only; no doctor check for WORKFLOW_PACK; no runbook; hub-link mode=alongside doesn't mention pack rules.
- **refs:** plan-T-HUB-051; plan-T-HUB-044; `.cursor/rules/shared/workflow-idea-pipeline.mdc`; T-HUB-046 alongside install.

**CREATIVE need:** нет.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| IDEA intent → pack | yaml table in idea-pipeline or `loop/workflow/intent_routing.yaml` | prose-only routing in chat |
| Doctor check | CLI JSON diagnostic codes | manual «did you set WORKFLOW_PACK?» |
| Pack install | hub-link `--pack <id>` copies rules + registers overlay | manual copy instructions only |

---

## Продуктовая spека (WHAT)

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Packs exist but operators don't know how to adopt | Docs + doctor + pipeline |
| 2 | Wedge | doctor check + runbook + IDEA table extension | Generated mainrule stub defer |
| 3 | Pre-mortem | Docs rot vs code | doctor encodes checks = living docs |
| 4 | Adoption | README + AGENTS.md section | |
| 5 | Leverage | T-HUB-044 doctor, T-HUB-046 hub-link | |
| 6 | Appetite | ~5–6 sNN, 3 days | |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator, я хочу `doctor --check workflow-pack` до loop start. | P0 | missing pack → non-zero + diagnostic |
| US-002 | Как ideator, я хочу IDEA PIPELINE `video` intent → video pack chain. | P0 | intent video_full → SCRIPT PLAN phase in idea md |
| US-003 | Как pack author, я хочу runbook «create pack in 30 min». | P0 | runbook steps match template 051 |
| US-004 | Как product repo, я хочу hub-link `--pack video-production` install rules. | P1 | alongside mode copies .cursor/rules/video |
| US-005 | Как loop user, я хочу `--workflow-pack` documented in loop help. | P1 | context_loop --help shows flag |

### Functional Requirements

- **FR-001:** `loop/workflow/intent_routing.yaml` — maps intent types → default pack + phase chain templates.
- **FR-002:** Extend `workflow-idea-pipeline.mdc` intent table with `video_production`, `content_factory` rows referencing pack ids (doc patch in harness/cursor export path per 046).
- **FR-003:** Doctor subcommand `doctor workflow-pack [--cwd]` — checks: resolve ok, phase_registry exists, rules_root exists, mb_root writable.
- **FR-004:** `docs/runbooks/workflow-pack-authoring.md` — step-by-step from template.
- **FR-005:** `docs/runbooks/workflow-pack-operator.md` — env vars, loop flags, troubleshooting.
- **FR-006:** hub-link extension `--pack <id>` (046 integration or standalone patch markers).
- **FR-007:** `loop/context_loop.py` — `--workflow-pack` CLI flag sets env for session (document parity with WORKFLOW_PACK).
- **FR-008:** AGENTS.md + CLAUDE.md section «Workflow Packs» with concise table.
- **FR-009:** pytest doctor workflow-pack matrix (ok pack, missing rules, invalid pack).
- **FR-010:** Update roadmap-harness-universal-runtime §2 table with Workflow Pack layer row.

### Success Criteria

| ID | Результат | Проверка |
|----|-----------|----------|
| SC-001 | doctor workflow-pack green on dev-hub default | CLI |
| SC-002 | doctor fails on invalid pack | pytest |
| SC-003 | IDEA intent video maps to pack | unit test intent_routing.yaml |
| SC-004 | Runbook paths exist and link from README | manual + link check |

### Assumptions

- Doc changes to `.cursor/rules/` go through harness/cursor materialization (046) or explicit user `implement this` for rules paths — plan lists targets; IMPLEMENT shard must include allowed paths.

### [НУЖНО УТОЧНИТЬ]

- n/a CRITICAL.

---

## AC+

1. doctor workflow-pack operational with ≥4 checks.
2. intent_routing.yaml loaded by IDEA PIPELINE workflow doc reference.
3. Operator runbook + author runbook committed.
4. hub-link --pack documented (implement or defer with explicit queue item — prefer implement P1).
5. pytest doctor pack matrix green.

### AC−

1. IDEA PIPELINE prose-only pack routing without yaml table.
2. Doctor warnings-only on invalid pack (must fail-closed for loop start recommendation).
3. Duplicate pack docs in 5 places without single runbook SoT.

---

## Техника / архитектура (HOW)

### intent_routing.yaml (draft)

```yaml
schema: workflow-intent-routing/v1
intents:
  video_production:
    pack: video-production
    pipeline:
      - { command: SCRIPT PLAN, gate: auto }
      - { command: SCRIPT DECOMPOSE, gate: auto }
      - { command: VISUAL STORYBOARD, gate: auto }
      - { command: POST EDIT, gate: approval }
      - { command: POST PUBLISH, gate: approval }
  feature_full:
    pack: dev-hub-software
    pipeline: []  # existing IDEA PIPELINE table remains canonical for software
```

### Files

| Path | Action |
|------|--------|
| `loop/workflow/intent_routing.yaml` | new |
| `loop/doctor/checks/workflow_pack.py` | new |
| `docs/runbooks/workflow-pack-authoring.md` | new |
| `docs/runbooks/workflow-pack-operator.md` | new |
| `bin/hub-link` or install script | --pack flag |
| `loop/context_loop.py` | --workflow-pack |
| `AGENTS.md`, `CLAUDE.md` | section |
| `loop/tests/test_doctor_workflow_pack.py` | new |

---

## Eng review spine

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| doctor resolve | invalid pack | resolve fail | exit 1 | TM-001 |
| rules_root | missing dir | is_dir | pack_rules_missing | TM-002 |
| phase_registry | missing | is_file | pack_phase_registry_missing | TM-003 |
| mb_root | not writable | access check | mb_root_not_writable | TM-004 |
| intent unknown | bad intent id | loader | fail-closed | TM-005 |

---

## Replacement / sunset

### A. Docs

| Prose-only IDEA video routing | intent_routing.yaml + doc ref | delete in-epic |

<a id="qa-consumes"></a>
## QA consumes

| ID | P | Scenario | Command | Expected |
|----|---|----------|---------|----------|
| TM-001 | P0 | doctor default ok | doctor workflow-pack | exit 0 |
| TM-002 | P0 | doctor invalid pack | fixture | exit 1 |
| TM-003 | P0 | intent load | pytest intent | PASS |
| TM-004 | P1 | hub-link pack dry-run | CLI | ok |
| TM-005 | P1 | loop --workflow-pack | pytest | PASS |

---

## Review readiness

| Gate | Status | Evidence |
|------|--------|----------|
| Product probe | done | §Product probe |
| Eng spine | done | filled |
| CREATIVE | n/a | — |
| qa_consumes | done | 5 TM |
| Plan review batch | done | below |

---

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Doctor as living docs | hub-link --pack P1 if 046 scope tight |
| Eng | Reuse doctor pattern from 044 | rules edit via harness/cursor path |

---

## До DECOMPOSE

1. s01 — intent_routing.yaml + loader  
2. s02 — doctor workflow-pack checks  
3. s03 — operator runbook  
4. s04 — author runbook  
5. s05 — context_loop --workflow-pack  
6. s06 — hub-link --pack (or doc defer)  
7. s07 — AGENTS/CLAUDE + idea-pipeline doc update  
8. s08 — pytest + roadmap table update  

---

## Appetite

| timebox_days | 3 |
| cut_list | `['hub-link --pack auto install', 'MCP doctor expose']` |

---

## Следующий режим

→ BACK DECOMPOSE T-HUB-052
