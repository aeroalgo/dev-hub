# [T-HUB-072 | context-bundle-fail-closed] PLAN

**Дата:** 2026-09-06  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** `memory-bank/back/clarify/clarify-20260906-loop-session-architecture.md`  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `loop-session-architecture-20260906`  
**Deps:** **hard T-HUB-071** (bundle манифест строится от identity; path-only бессмыслен, если COMMAND врёт). Soft T-HUB-057 (mb-load JSON). Soft T-HUB-063 (forbidden_for_parent sunset — **consume sidecar later**; this epic = missing file + md inline).  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns  
**Источник:** architecture §1.2 B P0.4; session audit §3 SessionStart inline plan.md; `loop/mb_load/session.py`

→ [decompose-index.md](decompose-index.md) · [decompose-index.yaml](../yaml/decompose-index.yaml)

---

## Контекст

- **req:** ContextBundle typed, completeness fail-closed. Markdown plan в load_now = **path + sha**, тело **не** инлайнится в SessionStart additionalContext. Любой required `missing_file:*` / `read_error:*` → `MbLoadResult.ok=false` + diagnostic_codes. Агент читает plan через Read, не через ложный «файл уже в контексте».
- **gap:**
  1. `loop/mb_load/session.py`: missing file `continue` then **`ok_status = True`** (L66–70, L97) — partial bundle looks successful.
  2. SessionStart инлайнит тела load_now (cap 256 KiB) including entire `plan.md` on DECOMPOSE/ANALYZE — breaks lean load, stale-in-context.
  3. `load_plan_section` splits plan by `##` (md-parsing, not canon) — optional path; this epic: **do not** use heading split as SoT; path-only for `**/md/plan.md`.
  4. SessionStart exception → `Warning: load_session exception` continue (architecture).
- **refs:** `loop/mb_load/session.py`; `loop/mb_load/resolver.py`; `harness/hooks/session-start.py`; architecture §1.3 forbidden inline; token-economy §0.5.1.
- **Не:** identity COMMAND (071); overlay (070); dirty_files abort (073); sunset forbidden_for_parent full ACL (063 leftover consume — if sidecar exists, skip inline those paths; **not** register schema).

**CREATIVE need:** нет.

---

## Technology axiom

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Bundle completeness | `MbLoadResult.ok` false if required missing | ok=true + missing_file diagnostic |
| Markdown plan | path_ref + sha256, `inline_body=false` | full plan.md in additionalContext |
| yaml/json artifacts | inline ≤ cap **only if** `inline=true` policy (implement yaml OK small) | silent truncate as success without truncated flag **and** ok true for required overflow? truncated may ok with flag; missing not ok |
| plan sections | yaml anchors / not SoT | `load_plan_section` `##` as COMMAND/AC |
| SessionStart exception | fail-closed diagnostic | Warning continue as success |

---

## Продуктовая спека (WHAT)

1. `load_session`: if any `missing_file:` or `read_error:` on **required** load_now paths → `ok=False`.
2. Policy: all load_now paths from AC are required unless marked optional (today none optional → all required).
3. Files matching `**/md/plan.md` or `plan-*.md` monolith: `MbLoadFile.content` empty or omitted; `sha256` of full file still computed (read for hash, **not** emit body to SessionStart). Alternative: don't read body into result.files used by inject; inject manifest only.
4. SessionStart additionalContext for md plan: `path + sha256 + size`, instruction «Read this path»; not the body.
5. yaml steps / qa yaml: may still inline under cap (needed for IMPLEMENT lean? IMPLEMENT should not have full plan anyway). Rule: **markdown plan/gap** path-only; **yaml/json** inline if ≤ cap.
6. Tests: missing file → ok false; plan.md fixture 400 lines → inject has no `# Heading` body from plan.

### Product probe

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Reframe | SessionStart врёт completeness и сжигает контекст plan | fail-closed + path-only |
| 2 | Wedge | ok=false on missing; skip inline for plan.md | P0 |
| 3 | Pre-mortem | Hash-only but still attach content «if small» | FR: plan.md never inline regardless size |
| 4 | Adoption | load_session + session-start inject | |
| 5 | Leverage | MbLoadResult already has ok/diagnostics | |
| 6 | Appetite | 3 days | cut: LoadNowItem.kind enum full product; sunset ACL (063) |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как DECOMPOSE, я не получаю тело plan.md в SessionStart. | P0 | fixture plan.md in load_now → files content empty / not in additionalContext |
| US-002 | Как runner, missing required file → ok false. | P0 | pytest missing_file → ok is False |
| US-003 | Как IMPLEMENT, yaml shard всё ещё может быть inline. | P1 | yaml in load_now has content if < cap |
| US-004 | Как агент, sha256 plan доступен чтобы заметить drift. | P1 | manifest sha matches file |
| US-005 | Как SessionStart, exception load_session не silent success. | P0 | hook diagnostic not ok |

#### Acceptance Scenarios — US-001

- **Given:** AC load_now includes `memory-bank/back/plan/T-HUB-062-…/md/plan.md` existing 500+ lines
- **When:** `load_session` + session start render
- **Then:** additionalContext does not contain unique plan sentence from line 50; contains path and sha256

#### Acceptance Scenarios — US-002

- **Given:** load_now path that does not exist
- **When:** `load_session`
- **Then:** `ok is False`; `missing_file:…` in diagnostic_codes; **not** ok True

### Functional Requirements

- **FR-001:** After the per-path loop, `ok_status = False` if any missing_file/read_error. Remove unconditional `ok_status = True` at L97. Combine with plan_section errors.
- **FR-002:** Classifier `is_markdown_plan_path(path)` : `md/plan.md` suffix, `plan-*.md` under memory-bank, gap-*.md optional same policy (architecture: plan/gap not inline).
- **FR-003:** For those paths: store sha256+size; `content=""` or omit from inject renderer; `truncated=False`; maybe `kind=path_ref` if schema allows extra field — **if extra=forbid** on MbLoadFile, use empty content + diagnostic `path_only:plan.md` **without** failing ok (file exists). Existence still required.
- **FR-004:** SessionStart renderer uses files.content only if non-empty; always lists paths.
- **FR-005:** `load_plan_section` not called from SessionStart hot path. If CLI still has flag — keep but SessionStart does not pass plan_section.
- **FR-006:** Cap: yaml overflow still truncated flag; required yaml truncated → ok false **or** documented ok true with truncated (choose: **ok false if truncated required yaml** to fail-closed — may be strict; Appetite: truncated yaml ok=true with truncated=true as today, **missing** not ok). Decision: **missing/read_error → ok false**; truncate → keep truncated flag, ok true (avoid blocking huge yaml). Plan md never truncated because not inlined.
- **FR-007:** Kind I: docs saying load_now bodies always inlined — rewrite.
- **FR-008:** Tests in `loop/tests/` for load_session.
- **FR-009:** Do not inline `decompose-index.md` (md coverage) — path-only same as plan. yaml index **may** inline (small).
- **FR-010:** forbidden_skipped from resolver still ok if policy skip; missing **required resolved** path not skipped → not ok.
- **FR-011:** SessionStart catch Exception: set inject warning **and** treat as incomplete (do not look like full success). Exact hook code as-built — find `load_session exception` and fail-closed.
- **FR-012:** Graphify N/A hub — n/a.

### Success Criteria

| ID | Result | Check | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | missing → ok false | pytest | outcome |
| SC-002 | plan.md not in inject body | pytest | outcome |
| SC-003 | yaml still inline | pytest | outcome |
| SC-004 | sha present for path-only | pytest | outcome |
| SC-005 | SessionStart exception not silent ok | pytest/hook | outcome |

### Assumptions

- IMPLEMENT load_now should already be yaml shard not plan; this epic still guards if plan sneaks in.
- 071 identity used for logging; bundle still loads from AC paths.

## AC

1. ok=false on missing required.
2. plan.md path-only in SessionStart.
3. yaml inline remains.
4. Independent tests as behavior.

### AC−

1. Нет ok=true при missing_file.
2. Нет «inline plan if < 256KiB».
3. Нет heading-split SoT on start.
4. Нет silent exception continue as success.
5. Нет dual loader (old inline + new path) both emitting body.

---

## Техника / архитектура (HOW)

- Fix `load_session` control flow; SessionStart inject filter.
- Pattern: Specification on path kind; fail-closed completeness.
- Sunset: `ok_status = True` after continue; full md content in files[].

---

## Eng review spine

### Data flow (ASCII)

```text
[AC load_now paths]
    -> [resolve_bundle_paths]           sync
    -> [read file / missing]            fail-closed ok
    -> [kind: plan.md → hash only]      no body
    -> [kind: yaml → inline ≤ cap]
    -> [MbLoadResult ok + diagnostics]
    -> [SessionStart additionalContext manifest]
```

### Failure matrix

| Component | Failure | Detection | Response | Test ID |
|-----------|---------|-----------|----------|---------|
| missing file ok true | false green | pytest | ok false | TM-001 |
| plan inline | context bloat / stale | pytest | path-only | TM-002 |
| yaml missing | same as missing | pytest | ok false | TM-003 |
| truncate yaml | truncated flag | pytest | ok true + flag | TM-004 |
| exception swallow | warning success | hook test | incomplete | TM-005 |
| load_plan_section start | md IPC | rg SessionStart | not called | TM-006 |
| index.md inline | bloat | path-only | TM-007 |
| sha mismatch later | drift | agent Read | 071/fingerprint | TM-008 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap |
|-----------|-----------|-----|
| Data flow complete | 5 | |
| Failure coverage | 5 | |
| Testability | 5 | tmp_path fixtures |

---

## Replacement / sunset

### A. Code / modules

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `ok_status = True` after missing continue | ok false | delete in-epic |
| inline plan.md content | path+sha | delete in-epic |
| SessionStart plan_section split | not on hot path | delete in-epic (call) |

### B. Entrypoints

| n/a | mb-load session CLI same | n/a |

### C. Fallbacks

| Warning continue exception as success | fail-closed incomplete | delete in-epic |

### I. Instruction surfaces

| «load_now files inlined» | path-only for md plan | delete in-epic |

### Path classifier (locked)

| Path glob | Inline body? | Hash? | Missing → ok |
|-----------|--------------|-------|--------------|
| `**/md/plan.md` | **never** | yes | false |
| `memory-bank/**/plan-*.md` monolith | **never** | yes | false |
| `**/gap-*.md` | **never** | yes | false |
| `**/decompose-index.md` | **never** | yes | false |
| `**/analyze-*.md` | **never** | yes | false |
| `**/*.yaml` / `**/*.yml` | yes if ≤ cap | yes | false |
| `**/*.json` state/qa | yes if ≤ cap | yes | false |
| optional marked path (none today) | n/a | n/a | true if optional |

### As-built sunset (session.py)

| Symbol / line (2026-09-06) | Behavior | Policy |
|----------------------------|----------|--------|
| missing_file `continue` then later `ok_status = True` | partial bundle looks OK | delete True; ok false if any missing/read_error |
| files[].content full md up to 256 KiB | SessionStart dumps plan | empty content for plan/gap md |
| `load_plan_section` `##` split | md IPC | not on SessionStart hot path |
| SessionStart `Warning: load_session exception` | continue as if load worked | incomplete / not success |

### Wire-complete

1. **Add** `is_markdown_plan_path` + ok aggregation.
2. **Wire** SessionStart renderer to skip empty content.
3. **Enforce** pytest missing + plan body absent.
4. **Purge** unconditional `ok_status = True`.

### Interaction with T-HUB-063 / 071

- 063 `forbidden_for_parent` ACL: if sidecar skip exists, skipped path is **not** missing (ok may stay true). This epic does **not** register ACL schema.
- 071 identity: bundle still reads AC `load_now` paths; COMMAND honesty is 071. This epic does not parse COMMAND.

---

## NFR

| ID | Requirement |
|----|-------------|
| NFR-1 | SessionStart context size not dominated by plan.md |
| NFR-2 | Completeness honest |
| NFR-3 | Hash cheap (read file once) |

---

## QA consumes

<a id="qa-consumes"></a>

### Scope

- load_session, session-start inject filter.
- Out: identity COMMAND (071), overlay (070).

### Test matrix

| ID | Priority | Scenario | Command | Expected | Maps |
|----|----------|----------|---------|----------|------|
| TM-001 | P0 | missing file | pytest load_session | ok false | US-002 |
| TM-002 | P0 | plan.md no body | pytest | content empty in inject | US-001 |
| TM-003 | P0 | yaml inline | pytest | content present | US-003 |
| TM-004 | P1 | sha path-only | pytest | sha256 len 64 | US-004 |
| TM-005 | P0 | exception incomplete | pytest hook | not success | US-005 |
| TM-006 | P1 | no plan_section on start | rg | 0 call | FR-005 |
| TM-007 | P1 | index.md path-only | pytest | | FR-009 |
| TM-008 | P1 | read_error ok false | pytest | | FR-001 |

---

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY | L3 | done | |
| Eng spine | L2+ | done | |
| §0.11 | | done | load_now path ↔ file ↔ inject |
| CREATIVE | | n/a | |
| qa_consumes | L2+ | done | |
| Plan review batch | L2+ | done | |

## Plan review batch log

| Phase | Auto-resolved | Deferred | Taste |
|-------|---------------|----------|-------|
| Product | plan never inline even if small | LoadNowItem.kind product | |
| Eng | fail-closed missing | sunset ACL 063 | |

---

## До DECOMPOSE

1. s01 — red tests missing ok + plan inline.
2. s02 — load_session ok_status fix.
3. s03 — path-only classifier + inject renderer.
4. s04 — SessionStart exception path.
5. s05 — Kind I + yaml still inline tests.
6. s06 — purge.

---

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | |
| `cut_list` | `['LoadNowItem.kind enum rollout', 'sunset forbidden_for_parent consume (063)', 'plan yaml section offsets']` | |

## Independent Test

- PASS: missing → not ok; plan.md body absent from inject; yaml present.
- FAIL: «cap 256KiB enough so inline OK».

## Следующий режим

→ BACK DECOMPOSE T-HUB-072 after 071.

**CREATIVE need:** нет.
