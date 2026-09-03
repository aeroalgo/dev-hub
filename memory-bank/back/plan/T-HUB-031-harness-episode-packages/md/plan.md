# [T-HUB-031 | harness-episode-packages] PLAN

**Дата:** 2026-08-31  
**Режим:** BACK PLAN  
**Уровень:** L3–L4  
**Статус:** active  
**Roadmap:** [roadmap-harness-maturity-borrowings-epics.md](roadmap-harness-maturity-borrowings-epics.md)  
**Queue:** [roadmap-harness-maturity-borrowings-epics.queue.yaml](roadmap-harness-maturity-borrowings-epics.queue.yaml)  
**Deps:** **hard** T-HUB-030 (wired trace/events/tier0).

**Skills:** writing-plans · architecture-patterns · python-testing-patterns · diagnosing-bugs

→ [T-HUB-031-harness-episode-packages/md/decompose-index.md](T-HUB-031-harness-episode-packages/md/decompose-index.md) — **после DECOMPOSE**

---

## Контекст

- **req:** Каждая loop-итерация (prepare → agent → check_after) produces an **auditable episode package** — structured bundle for postmortem, replay analysis, and incident correlation (arXiv Harness Engineering H3: episode package with evidence structure).
- **gap:** `session-trace.jsonl` — append-only tail only; нет immutable bundle per session; failure attribution scattered across checkpoint, incidents, events.
- **refs:** chat 2026-08-31 P1-6; `loop/incidents/trace.py`; `loop/schemas/`; T-HUB-017 observability.

**CREATIVE need:** нет.

---

## Цель

После каждой loop-сессии в `runtime/<slug>/episodes/<episode_id>/` появляется **versioned bundle** с детерминированным manifest, пригодный для diff между успешными/неуспешными runs и для incident postmortem.

---

## Продуктовая спека (WHAT)

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как operator после halt, я хочу открыть episode folder и увидеть полный контекст сессии, чтобы не читать raw chat log. | P0 | episode dir contains manifest + artifacts |
| US-002 | Как auditor, я хочу episode_id в incidents.jsonl и events, чтобы correlate incident ↔ session. | P0 | incident metadata includes episode_id |
| US-003 | Как developer, я хочу pytest log и verify verdict в bundle, чтобы воспроизвести gate failure. | P1 | bundle includes gate_verdict sidecar ref |
| US-004 | Как platform, я хочу retention policy для episodes, чтобы disk не рос бесконечно. | P1 | EPIC_EPISODE_RETENTION_DAYS prunes old dirs |

#### Acceptance Scenarios — US-001

- **Given:** loop completes check_after (continue or halt)
- **When:** episode finalized
- **Then:** `episodes/<episode_id>/manifest.json` schema `loop-episode/v1` with prompt_hash, fingerprint_before/after, armed_step, decide action, artifact refs

### Functional Requirements (FR-###)

- **FR-001:** Schema `loop/schemas/episode.py` — `EpisodeManifest` fields: episode_id, started_at, ended_at, epic_id, role, armed_step, sNN, prompt_hash, fingerprint_before, fingerprint_after, decide, halt_reason, incident_ids[], event_seq_range, load_now_paths[], load_now_sha256[].
- **FR-002:** Module `loop/episodes/` — `begin_episode(cwd)`, `finalize_episode(cwd, check_after_result)`, `episode_dir(cwd, episode_id)`.
- **FR-003:** `prepare_session` calls `begin_episode`; `check_after` calls `finalize_episode`.
- **FR-004:** Bundle files (copies or symlinks — **copies** for immutability): `manifest.json`, `check_after.json`, `checkpoint_snapshot.json`, optional `gate_verdict.json`, `trace_tail.jsonl` (last N lines).
- **FR-005:** `append_trace` includes `episode_id` field when active.
- **FR-006:** Incidents opened during session store `episode_id` in metadata.
- **FR-007:** CLI `context_loop.py episode-list [--last N]` and `episode-show <id>`.
- **FR-008:** Retention: `prune_episodes(cwd, days=EPIC_EPISODE_RETENTION_DAYS default 30)` callable from doctor or cron doc.
- **FR-009:** Tests: manifest schema, finalize on continue/halt, episode_id correlation, retention prune.

### Success Criteria (SC-###)

| ID | Result | Verify |
| :--- | :--- | :--- |
| SC-001 | Episode created every loop iteration | integration test loop canary |
| SC-002 | manifest validates against pydantic schema | pytest |
| SC-003 | incident carries episode_id | pytest store |
| SC-004 | episode-list CLI works | pytest CLI |

### Assumptions

- No secrets in episode bundle (reuse epic_events forbidden metadata rules).
- Bundle size bounded: no full session chat log by default; optional `EPIC_EPISODE_INCLUDE_PROMPT=1` for debug.

---

## AC

1. `loop-episode/v1` schema + pydantic model.
2. begin/finalize wired in prepare/check_after.
3. episode_id in trace + incidents.
4. episode-list / episode-show CLI.
5. Retention documented + prune function tested.
6. README § Episodes.

---

## Техника / архитектура (HOW)

```
runtime/<slug>/episodes/
  <episode_id>/
    manifest.json
    check_after.json
    checkpoint_snapshot.json
    gate_verdict.json      # if exists
    trace_tail.jsonl
```

**Episode ID:** `{utc_compact}_{epic_id_short}_{seq}` or uuid4 — DECOMPOSE picks one; must be sortable.

### Replacement / sunset

n/a greenfield additive.

---

## До DECOMPOSE (черновик)

| sNN | Slice |
|-----|-------|
| s01 | episode schema + begin/finalize skeleton |
| s02 | wire prepare/check_after |
| s03 | artifact copies + load_now hash snapshot |
| s04 | incident/trace correlation |
| s05 | episode-list/show CLI |
| s06 | retention prune + tests + README |

---

## Следующий режим

→ BACK DECOMPOSE
