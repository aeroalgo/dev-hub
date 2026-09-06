# [T-HUB-064 | video-pack-route-verify-parity] PLAN

**Дата:** 2026-09-05  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260905-workflow-loop-audit.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `workflow-loop-20260905`  
**Deps:** soft T-HUB-051 (reference video pack planned). Hard нет — leftover **executable routes + manifest agents**. Не ждать 051 IMPLEMENT.  
**Skills:** writing-plans · architecture-patterns · python-testing-patterns  
**Источник:** audit `01-subagents-prompts.md` P0 · `02-workflow-pack-and-rules.md` video routes · `08` matrix video rows

→ decompose: [md/decompose-index.md](decompose-index.md) · machine [../yaml/decompose-index.yaml](../yaml/decompose-index.yaml) (status SoT). Plan не дублирует чеклист шагов.

---

## Контекст

- **req:** Pack `video-production` не может быть `ok=True`, если `route_command()` строит несуществующие role-subdir paths, а `verify-script/edit/publish` отсутствуют в manifest. Operator на `SCRIPT PLAN` должен получить **существующий** workflow file + materialized verify agent + stop mapping.
- **gap (as-built):**
  1. `harness/agents/verify-script.md`, `verify-edit.md`, `verify-publish.md` существуют (11 prompt files).
  2. `harness/manifest.yaml` описывает 8 agents — **без** трёх video.
  3. Parity checker зелёный, потому что сравнивает только manifest members, не `harness/agents/*.md`.
  4. `route_command()` строит role-subdirectory paths, которых нет (audit 02).
  5. Phase registry video указывает verify agents; stop `VERIFY_FINISH_AGENTS` их не знает.
  6. T-HUB-051 plan уже требует FR-005 agents + FR-004 rules skeleton — **не закрыто**. Этот эпик = **исполняемый leftover**: routes exist XOR route_map to shared files; manifest rows; parity source-driven; e2e route exists.
- **refs:** `workflows/video/phase_registry.yaml`; `loop/workflow/resolve.py` `route_command`; `harness/manifest.yaml`; `.codex/agents/`; `loop/tests/test_workflow_pack_video_e2e.py`.
- **Не:** ffmpeg real render (051 CREATIVE/tool gate); software verify rewrite; 067 full doctor (consumes this).

### CREATIVE need

**нет** (051 already flagged CREATIVE for tool-gate; this leftover is engineering parity). Если 051 CREATIVE ещё не шёл — не блокируем 064.

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Route | existing path on disk or explicit `route_map` | `ok=true` + missing file |
| Verify agents | every `harness/agents/*.md` declared in manifest or `advisory/unmaterialized` with reason | parity green while prompt file orphan |
| Video verify | same stop/validate pipeline as software verify-* | silent skip because not in hardcoded set |
| Phases without verify | `no_gate_reason` machine field | implicit skip BRIEF/STORYBOARD/SHOOT |

---

## Продуктовая спека (WHAT)

1. Каждая команда intent pipeline video (`SCRIPT PLAN`, `VISUAL STORYBOARD`, `POST EDIT`, `POST PUBLISH`, … из pack) резолвится в **существующий** workflow path.
2. Три verify prompt-файла либо в manifest+materialize Claude/Codex, либо явно excluded с кодом (выбор: **include** — audit preferred).
3. `route_command` never returns ok with nonexistent workflow.
4. Stop mapping знает video verify agents.
5. Phases without verify documented as no-gate.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | Video pack — декорация | Executable graph |
| 2 | Wedge | manifest 3 agents + route files exist test | P0 |
| 3 | Pre-mortem | Добавят manifest, route всё ещё 404 | FR route_command exists |
| 4 | Adoption | WORKFLOW_PACK=video-production SCRIPT PLAN | |
| 5 | Leverage | 051 skeleton; don't rewrite pack framework | |
| 6 | Appetite | 4 days | cut: real ffmpeg, full video rules prose |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator SCRIPT PLAN, я хочу route на существующий workflow. | P0 | Path.exists(route_command result) |
| US-002 | Как Codex, я хочу TOML для verify-edit. | P0 | `.codex/agents/verify-edit.toml` after materialize |
| US-003 | Как parent EDIT, я хочу SubagentStop принять gate JSON verify-edit. | P0 | agent in VERIFY set |
| US-004 | Как CI, я хочу parity fail если agents/*.md не в manifest. | P0 | orphan prompt fixture |

#### Acceptance Scenarios — US-001

- **Given:** `WORKFLOW_PACK=video-production`
- **When:** `route_command("SCRIPT PLAN")` (точный argv из intent_routing)
- **Then:** `ok` и Path.exists; missing dir → ok false `pack_route_missing`

### Functional Requirements

- **FR-001:** Inventory всех video intent commands vs FS.
- **FR-002:** Либо создать missing `workflow-*.mdc` under video role dirs, либо `route_map` на реальные shared files — **один** SoT, не оба.
- **FR-003:** Manifest entries `verify-script`, `verify-edit`, `verify-publish` с claude copy_to + codex materialize.
- **FR-004:** Parity source = `harness/agents/*.md` set, not `REQUIRED_CODEX_AGENTS` hardcoded allowlist-only.
- **FR-005:** Stop/start contracts include three ids (VERIFY_FINISH or phase-aware map).
- **FR-006:** BRIEF/STORYBOARD/SHOOT: `no_gate_reason` in phase_registry.
- **FR-007:** pytest: each intent command path exists; broken fixture `pack_route_missing`.
- **FR-008:** `bin/runtime-sync --check` includes new TOML or documents generate step.
- **FR-009:** Kind I: pack README не утверждает «fully wired» пока FR-007 red.
- **FR-010:** Не reuse verify-implement contract verbatim (051 axiom) — keep distinct prompts, wire same **pipeline**.
- **FR-011:** JANITOR no-gate (audit 02 §7) **не** в этом эпике кроме если video janitor — skip.

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | 0 missing video routes | pytest e2e | outcome |
| SC-002 | 3 video agents in manifest+toml | files | outcome |
| SC-003 | orphan prompt fails parity | pytest | outcome |
| SC-004 | no_gate_reason on ungated phases | yaml+test | outcome |

### Assumptions

- Не реализуем полный video producer UX.
- Software pack routes не ломаем.

## AC

1. route_command video commands → existing files.
2. Three agents materialized both runtimes.
3. Parity fails on undeclared prompt file.
4. Stop validates video verify JSON like software.

### AC−

1. Нет ok=true + missing path.
2. Нет parity green на subset manifest.
3. Нет silent skip video verify.
4. Нет dual route_map + ghost role-subdir без delete.
5. Нет copy verify-implement as video SoT.

## HOW

- `loop/workflow/resolve.py` route builder; `workflows/video/**`; `harness/manifest.yaml`; materializers; `_lib.py` agent sets; tests `test_workflow_pack_video_e2e.py`, `test_workflow_pack_phase_router.py`.
- Decision recorded in plan: prefer **create role workflow files** if index already documents SCRIPT/VISUAL/POST dirs; if dirs will never exist, route_map only and **delete** code that concatenates missing subdirs.

## Eng review spine

### Data flow

```text
[SCRIPT PLAN] -> [pack resolve] -> [route_command path]
                    fail-closed        Path.exists
[parent spawn verify-edit] -> [manifest] -> [materialize toml/md]
                    -> [SubagentStop VERIFY set] -> [gate schema]
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| missing workflow file | route 404 | exists check | pack_route_missing | TM-001 |
| orphan agent md | parity green false | source-driven parity | fail | TM-002 |
| video verify not in stop set | verdict ignored | mapping test | add ids | TM-003 |
| BRIEF has fake verify | spawn fail | no_gate_reason | document | TM-004 |
| Codex toml missing | runtime-sync | check | materialize | TM-005 |
| software route regression | software pack e2e | pytest | halt | TM-006 |
| dual ghost dirs | two SoT | rg role-subdir builder | purge one | TM-007 |

### Eng spine self-check

| Dimension | Score | Gap |
|-----------|-------|-----|
| Data flow complete | 5 | |
| Failure coverage | 5 | |
| Testability | 4 | need fixture pack |

## Replacement / sunset

### A

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `REQUIRED_CODEX_AGENTS` as sole parity source | agents dir glob ∪ manifest declare | delete in-epic (hardcoded exclusive set) |
| route builder to nonexistent role-subdir | existing files / route_map | delete in-epic |
| parity skip video | include | delete in-epic |

### B

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| Codex without video toml | generated toml | delete in-epic |

### C

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| ok=true on missing route | fail-closed | delete in-epic |
| «Claude symlink enough» | manifest declare | delete in-epic |

### I

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| docs «video pack works» | honest after tests | delete in-epic |
| CLAUDE.md pack table if claims full video execute | match reality | delete in-epic |

## QA consumes

<a id="qa-consumes"></a>

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | SCRIPT PLAN path exists | pytest video e2e | PASS | US-001 |
| TM-002 | P0 | missing route fixture | pytest | pack_route_missing | FR-007 |
| TM-003 | P0 | manifest has 3 video agents | yaml+pytest | PASS | FR-003 |
| TM-004 | P0 | orphan md fails parity | pytest | fail | US-004 |
| TM-005 | P0 | stop mapping verify-edit | unit | in set | FR-005 |
| TM-006 | P1 | software pack still routes | pytest software | PASS | AC software |

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | |
| Eng review spine | L2+ | done | |
| §0.11 | n/a | n/a | |
| CREATIVE | n/a | n/a | 051 owns tool-gate creative |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred |
|-------|---------------|----------|
| Product | Include agents, don't advisory-exclude | ffmpeg |
| Eng | Source-driven parity | full doctor 067 |

## До DECOMPOSE

1. s01 — inventory commands vs FS (red tests).
2. s02 — fix route_command / add workflow files XOR route_map; purge ghost builder.
3. s03 — manifest + materialize 3 agents.
4. s04 — stop/start mapping + no_gate_reason.
5. s05 — source-driven parity (orphan fail).
6. s06 — Kind I + software regression.
7. s07 — purge leftover hardcoded REQUIRED_CODEX_AGENTS exclusivity.

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `4` | |
| `cut_list` | `['ffmpeg live gate', 'full video rules prose', 'template pack authoring']` | 051 leftover |

## Independent Test

- PASS: SCRIPT PLAN path exists; verify-edit.toml exists; orphan md fails.
- FAIL: «manifest yaml has keys» without files; «prompt files exist» without manifest.

## Следующий режим

→ BACK ANALYZE T-HUB-064-video-pack-route-verify-parity (DECOMPOSE done; ANALYZE обязателен, не deferred).

### CREATIVE need

**нет.**
