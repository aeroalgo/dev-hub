# [T-HUB-051 | workflow-pack-reference-video] PLAN

**Дата:** 2026-09-02  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-workflow-pack-framework-epics.md](roadmap-workflow-pack-framework-epics.md)  
**Queue:** [roadmap-workflow-pack-framework-epics.queue.yaml](roadmap-workflow-pack-framework-epics.queue.yaml)  
**Deps:** **hard** T-HUB-049 (phase router), T-HUB-050 (mb paths). **Soft:** T-HUB-046 (hub-link install rules tree).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · modern-python

→ [decompose-T-HUB-051-workflow-pack-reference-video/index.md](decompose-T-HUB-051-workflow-pack-reference-video/index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Registry + router + paths без reference pack — абстракция без proof. Нужен **reference Workflow Pack `video-production`**: phases BRIEF→SCRIPT→STORYBOARD→SHOOT→EDIT→PUBLISH, roles SCRIPT/VISUAL/POST, verify agents, optional **external tool gate** (ffmpeg file check), rules skeleton, e2e pytest proving non-software pipeline runs on harness.
- **gap:** No second pack row; no non-BACK command prefix in production; no external tool gate pattern; no pack authoring template.
- **refs:** plan-T-HUB-048/049/050; чат 2026-09-02 video example; harness/agents/verify-*.md pattern.

**CREATIVE need:** да — §Creative batch: external tool gate contract (machine check vs LLM verdict) — 1 session перед IMPLEMENT s05.

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| External tool gate | CLI adapter → JSON `{ok, diagnostic_codes[]}` | LLM prose «render готов» |
| Video phase gates | pack phase_registry yaml | copy software IMPLEMENT gates for EDIT |
| Verify agents | harness/agents/verify-edit.md etc. | reuse verify-implement contract verbatim |
| Pack overlay | hub registry row + workflows/video/manifest.yaml | duplicate registry files per product |

---

## Продуктовая spека (WHAT)

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | No proof that harness works outside software | Reference pack + e2e |
| 2 | Wedge | 6 phases + 1 external gate (ffmpeg duration) | Full pipeline defer |
| 3 | Pre-mortem | Video pack rots; rules not installed | hub-link pack install doc in 052 |
| 4 | Adoption | Operator sets WORKFLOW_PACK=video-production | README in workflows/video/ |
| 5 | Leverage | Existing verify/spawn/stop-gate | New verify-* md only |
| 6 | Appetite | ~8–10 sNN, 6 days | |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как video producer, я хочу SCRIPT PLAN создал plan под memory-bank/video/script/. | P0 | arm_phase SCRIPT PLAN → correct mb path |
| US-002 | Как operator EDIT, я хочу external gate проверил output mp4 exists + duration>0. | P0 | tool gate fail without file; pass with fixture mp4 |
| US-003 | Как parent, я хочу verify-edit spawn после IMPLEMENT gate как в software. | P0 | stop-gate blocks FINISH until verify PASS |
| US-004 | Как pack author, я хочу template workflows/_template/ для нового pack. | P1 | copy template → validate registry |
| US-005 | Как CI, я хочу e2e pytest video pack без real ffmpeg render. | P0 | mock external gate adapter |

#### Acceptance Scenarios — US-002

- **Given:** EDIT step finished, no `outputs/final.mp4`
- **When:** `epic_resolve.py tool-gate check --gate render --cwd $PROJECT_ROOT`
- **Then:** exit 1, `{ok:false, diagnostic_codes:["render_output_missing"]}`

### Functional Requirements

- **FR-001:** Add `video-production` row to `workflow_pack_registry.yaml` (or overlay merge from `workflows/video/manifest.yaml`).
- **FR-002:** `workflows/video/phase_registry.yaml` — phases BRIEF, SCRIPT, STORYBOARD, SHOOT, EDIT, PUBLISH with finish_gates + verify_agent mapping.
- **FR-003:** Roles: script, visual, post; prefixes SCRIPT, VISUAL, POST.
- **FR-004:** `.cursor/rules/video/` skeleton: mainrule + workflow-plan/implement/qa + `_lean/` gates (minimal viable, mirror back_developer structure).
- **FR-005:** `harness/agents/verify-script.md`, `verify-edit.md`, `verify-publish.md` (phase-specific contracts).
- **FR-006:** `loop/workflow/tool_gates/` — protocol `ToolGateAdapter`, registry in pack manifest `tool_gates: {render: ...}`.
- **FR-007:** `workflows/video/tools/render_check.py` — ffmpeg/ffprobe or stat fallback; JSON stdout contract.
- **FR-008:** CLI `epic_resolve.py tool-gate check --gate <id>`.
- **FR-009:** Integrate tool gate into stop-gate / FINISH path for phases declaring `external_gates: [render]` in phase_registry extension field.
- **FR-010:** `workflows/_template/` — manifest, phase_registry stub, rules README.
- **FR-011:** pytest e2e: resolve video pack → arm EDIT → mock tool gate → verify spawn contract (no real LLM).
- **FR-012:** Sample epic fixture `memory-bank/video/script/plan/decompose-T-VIDEO-001-demo/` for tests.

### Success Criteria

| ID | Результат | Проверка |
|----|-----------|----------|
| SC-001 | WORKFLOW_PACK=video-production resolves | CLI |
| SC-002 | SCRIPT IMPLEMENT gates differ from BACK IMPLEMENT | pytest |
| SC-003 | tool-gate check render fail/pass | pytest |
| SC-004 | e2e harness smoke video pack | pytest |
| SC-005 | Template pack validates | pytest |

### Assumptions

- ffmpeg optional; render_check degrades to file size/duration mock in CI.
- Video rules are reference quality, not production-polished copywriting.
- CREATIVE resolves external_gates schema extension in phase-registry v1.1 or pack overlay fields.

### [НУЖНО УТОЧНИТЬ]

- Soft: phase-registry schema extension for `external_gates[]` — decide in CREATIVE (additive yaml field vs sidecar).

---

## AC+

1. video-production pack end-to-end resolvable.
2. At least one external tool gate enforced on EDIT phase.
3. Three verify agent contracts for video phases.
4. Template pack for authors.
5. Software pack unaffected when video pack enabled on separate PROJECT_ROOT fixture.

### AC−

1. Hardcoded `if video` in stop-gate body.
2. Real ffmpeg required in CI pytest.
3. Video pack replaces default software pack globally.
4. Dual phase registry loader for video only.

---

## Техника / архитектура (HOW)

### video phase_registry (draft excerpt)

```yaml
phases:
  EDIT:
    arm_template: implement
    finish_gates_dict:
      mode: implement
      need_verify: true
      need_reviewer: false
    verify_agent: verify-edit
    external_gates: [render]
    dsh_preset: implement
```

### Tool gate protocol

```python
class ToolGateAdapter(Protocol):
    id: str
    def check(self, ctx: ToolGateContext) -> ToolGateResult: ...
```

### Files

| Path | Action |
|------|--------|
| `workflows/video/manifest.yaml` | new |
| `workflows/video/phase_registry.yaml` | new |
| `workflows/_template/**` | new |
| `.cursor/rules/video/**` | new skeleton |
| `harness/agents/verify-script.md` etc. | new |
| `loop/workflow/tool_gates/` | new package |
| `workflows/video/tools/render_check.py` | new |
| `loop/tests/test_workflow_pack_video_e2e.py` | new |
| `loop/workflow_pack_registry.yaml` | add video row |

---

## Eng review spine

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| render_check | no output file | stat fail | render_output_missing | TM-001 |
| ffmpeg missing | binary absent | optional degrade | diagnostic ffmpeg_optional | TM-002 |
| verify-edit spawn | no AC+ | spawn-hard | deny | TM-003 |
| pack rules missing | hub-link not run | doctor 052 | warning pack_rules_missing | TM-004 |
| software cross-contam | wrong mb root | parity test | block merge | TM-005 |

---

## Replacement / sunset

n/a greenfield reference pack (additive registry row).

<a id="qa-consumes"></a>
## QA consumes

| ID | P | Scenario | Command | Expected |
|----|---|----------|---------|----------|
| TM-001 | P0 | render gate fail | tool-gate check | exit 1 |
| TM-002 | P0 | render gate pass | fixture mp4 | exit 0 |
| TM-003 | P0 | Video pack resolve | workflow resolve | ok |
| TM-004 | P0 | EDIT verify gate | e2e pytest | PASS |
| TM-005 | P1 | Template validates | pytest template | PASS |
| TM-006 | P0 | Software isolation | parity pytest | PASS |

---

## Review readiness

| Gate | Status | Evidence |
|------|--------|----------|
| Product probe | done | §Product probe |
| Eng spine | done | filled |
| CREATIVE | Required | external_gates schema — before IMPLEMENT s05 |
| qa_consumes | done | 6 TM |
| Plan review batch | done | below |

---

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Reference only; not default pack | Remote pack registry marketplace → out of scope |
| Eng | ToolGateAdapter mirrors RuntimeAdapter thinness | CREATIVE for external_gates yaml field |

---

## До DECOMPOSE

1. s01 — video manifest + registry row  
2. s02 — phase_registry.yaml  
3. s03 — rules/video skeleton  
4. s04 — verify agents (script, edit, publish)  
5. s05 — tool_gates package + render_check (after CREATIVE)  
6. s06 — stop-gate external_gates integration  
7. s07 — workflows/_template  
8. s08 — e2e pytest + fixtures  
9. s09 — docs workflows/video/README.md  

---

## Appetite

| timebox_days | 6 |
| cut_list | `['real ffmpeg integration test', 'full VISUAL/POST rules polish']` |

---

## Следующий режим

→ BACK CREATIVE (external_gates schema) **или** BACK DECOMPOSE T-HUB-051
