# Реестр шагов (Decompose index)
**Plan ID:** T-HUB-051-workflow-pack-reference-video  
**План:** [plan.md](plan.md)  
**Machine index:** [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) — **канон status**  
**Дата:** 2026-09-05  
**Режим:** BACK DECOMPOSE

Каждый шаг — атомарная задача. Shard: `sNN-<slug>.yaml` — шаблон [epic-step.yaml](/.cursor/templates/decompose/epic-step.yaml).

> **Path (layout v2 HARD):** этот файл = `plan/T-HUB-051-workflow-pack-reference-video/md/decompose-index.md`. Machine = `plan/T-HUB-051-workflow-pack-reference-video/yaml/decompose-index.yaml`. Shards = `yaml/steps/`. **FORBIDDEN** `decompose-<id>/` · дубль имён.

---

## Skills в контексте

| Skill | Зачем |
|-------|-------|
| `writing-plans` | структура шагов, атомарность |
| `python-testing-patterns` | pytest e2e + fixtures + mock adapter |
| `architecture-patterns` | ToolGateAdapter Protocol, pack overlay |
| `modern-python` | Protocol, TypedDict, Pydantic v2 |

---

## Requirements coverage (plan → steps)

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный `out_of_scope` + `follow_up`.

| Req ID | Plan FR text (verbatim) | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-001 | Add `video-production` row to `workflow_pack_registry.yaml` (or overlay merge from `workflows/video/manifest.yaml`). | s01 | |
| FR-002 | `workflows/video/phase_registry.yaml` — phases BRIEF, SCRIPT, STORYBOARD, SHOOT, EDIT, PUBLISH with finish_gates + verify_agent mapping. | s02 | |
| FR-003 | Roles: script, visual, post; prefixes SCRIPT, VISUAL, POST. | s01, s02 | prefixes в manifest, roles в phase_registry |
| FR-004 | `.cursor/rules/video/` skeleton: mainrule + workflow-plan/implement/qa + `_lean/` gates (minimal viable, mirror back_developer structure). | s03 | |
| FR-005 | `harness/agents/verify-script.md`, `verify-edit.md`, `verify-publish.md` (phase-specific contracts). | s04 | |
| FR-006 | `loop/workflow/tool_gates/` — protocol `ToolGateAdapter`, registry in pack manifest `tool_gates: {render: ...}`. | s05 | |
| FR-007 | `workflows/video/tools/render_check.py` — ffmpeg/ffprobe or stat fallback; JSON stdout contract. | s05 | |
| FR-008 | CLI `epic_resolve.py tool-gate check --gate <id>`. | s06 | |
| FR-009 | Integrate tool gate into stop-gate / FINISH path for phases declaring `external_gates: [render]` in phase_registry extension field. | s06 | |
| FR-010 | `workflows/_template/` — manifest, phase_registry stub, rules README. | s07 | |
| FR-011 | pytest e2e: resolve video pack → arm EDIT → mock tool gate → verify spawn contract (no real LLM). | s08 | |
| FR-012 | Sample epic fixture `memory-bank/video/script/plan/decompose-T-VIDEO-001-demo/` for tests. | s08 | |
| AC+1 | video-production pack end-to-end resolvable. | s01, s02 | |
| AC+2 | At least one external tool gate enforced on EDIT phase. | s05, s06 | |
| AC+3 | Three verify agent contracts for video phases. | s04 | |
| AC+4 | Template pack for authors. | s07 | |
| AC+5 | Software pack unaffected when video pack enabled on separate PROJECT_ROOT fixture. | s08 | |
| AC−1 | Hardcoded `if video` in stop-gate body. | s06 | enforced by Protocol + dispatch |
| AC−2 | Real ffmpeg required in CI pytest. | s05, s08 | mock adapter pattern |
| AC−3 | Video pack replaces default software pack globally. | s01 | additive registry row |
| AC−4 | Dual phase registry loader for video only. | s02 | reuse load_phase_registry |
| US-001 | Как video producer, я хочу SCRIPT PLAN создал plan под memory-bank/video/script/. | s01, s02 | mb path from manifest.memory_bank |
| US-002 | Как operator EDIT, я хочу external gate проверил output mp4 exists + duration>0. | s05, s06 | |
| US-003 | Как parent, я хочу verify-edit spawn после IMPLEMENT gate как в software. | s04, s06 | |
| US-004 | Как pack author, я хочу template workflows/_template/ для нового pack. | s07 | |
| US-005 | Как CI, я хочу e2e pytest video pack без real ffmpeg render. | s08 | |
| SC-001 | WORKFLOW_PACK=video-production resolves | s01 | |
| SC-002 | SCRIPT IMPLEMENT gates differ from BACK IMPLEMENT | s02, s08 | |
| SC-003 | tool-gate check render fail/pass | s05, s06, s08 | |
| SC-004 | e2e harness smoke video pack | s08 | |
| SC-005 | Template pack validates | s07, s08 | |
| TM-001 | render gate fail — stat fail → render_output_missing | s05 | |
| TM-002 | render gate pass — fixture mp4 → exit 0 | s05, s08 | |
| TM-003 | Video pack resolve — workflow resolve → ok | s01 | |
| TM-004 | EDIT verify gate — e2e pytest | s08 | |
| TM-005 | Template validates — pytest template | s07, s08 | |
| TM-006 | Software isolation — parity pytest | s08 | |
| docs s09 | workflows/video/README.md | s09 | |

---

## Stages coverage (plan/canon → steps)

| Этап / фаза | Источник | sNN |
| :--- | :--- | :--- |
| Pack manifest + registry row (video-production) | plan §FR-001, §FR-003 | s01 |
| Phase registry YAML (6 phases + external_gates field) | plan §FR-002, phase_registry schema | s02 |
| Rules/video skeleton (.cursor/rules/video/) | plan §FR-004 | s03 |
| Verify agent contracts (script, edit, publish) | plan §FR-005, harness/agents pattern | s04 |
| ToolGateAdapter Protocol + render_check.py | plan §FR-006, §FR-007, §Technology axiom | s05 |
| CLI tool-gate check + stop-gate integration | plan §FR-008, §FR-009 | s06 |
| Pack authoring template (workflows/_template/) | plan §FR-010, §US-004 | s07 |
| pytest e2e + fixtures (mock gate, isolation) | plan §FR-011, §FR-012, §QA consumes | s08 |
| README + operator docs | plan §Product probe #4, §Appetite | s09 |

---

## Outcome map (plan → steps)

| Plan outcome / NFR / AC | Закрывают шаги |
| :--- | :--- |
| Proof that harness works outside software pipeline (reframe gap) | s01, s02, s03, s04, s08 |
| video-production pack resolves end-to-end via WORKFLOW_PACK env | s01, s02 |
| External tool gate enforced on EDIT (machine check vs LLM prose) | s05, s06 |
| Three verify agent contracts for video phases (SCRIPT, EDIT, PUBLISH) | s04 |
| Template pack for authors (copy → validate) | s07 |
| Software pack unaffected — isolation guarantee | s01 (additive row), s08 (parity test) |
| Operator can set WORKFLOW_PACK=video-production without config change | s01 |
| Non-BACK command prefix (SCRIPT/VISUAL/POST) in production | s01, s02 |
| Render gate fail/pass contract (JSON stdout, exit code) | s05, s06 |
| e2e pytest without real ffmpeg (CI-safe mock) | s05, s08 |
| Out of scope (не в этой нарезке) | — |
| Real ffmpeg integration test | — / cut_list |
| Full VISUAL/POST rules polish | — / cut_list |
| Remote pack registry marketplace | — / T-HUB-052 follow-up |

---

## Replacement cleanup (plan → steps)

> Greenfield additive reference pack — нет замен существующего prod кода.

| Устаревает (path / symbol) | Kind | Замена | sNN (deletes) | Fallback? | Notes |
| :--- | :---: | :--- | :--- | :---: | :--- |
| n/a — нет замен | — | — | — | — | greenfield additive |

---

## Очередь шагов (BACK)

| step_id | title & files | needs_creative | tdd | next_phase | status |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **s01** | [s01-video-manifest-registry-row.yaml](../yaml/steps/s01-video-manifest-registry-row.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s02** | [s02-video-phase-registry-yaml.yaml](../yaml/steps/s02-video-phase-registry-yaml.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s03** | [s03-cursor-rules-video-skeleton.yaml](../yaml/steps/s03-cursor-rules-video-skeleton.yaml) | no | no | BACK IMPLEMENT | completed |
| **s04** | [s04-verify-agents-script-edit-publish.yaml](../yaml/steps/s04-verify-agents-script-edit-publish.yaml) | no | no | BACK IMPLEMENT | completed |
| **s05** | [s05-tool-gate-adapter-render-check.yaml](../yaml/steps/s05-tool-gate-adapter-render-check.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s06** | [s06-cli-tool-gate-check-stop-gate.yaml](../yaml/steps/s06-cli-tool-gate-check-stop-gate.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s07** | [s07-workflows-template-pack-authoring.yaml](../yaml/steps/s07-workflows-template-pack-authoring.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s08** | [s08-e2e-pytest-video-pack-fixtures.yaml](../yaml/steps/s08-e2e-pytest-video-pack-fixtures.yaml) | no | yes | BACK IMPLEMENT | completed |
| **s09** | [s09-readme-operator-docs.yaml](../yaml/steps/s09-readme-operator-docs.yaml) | no | no | BACK IMPLEMENT | completed |