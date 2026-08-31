# Audit Callers repair_* & Sunset Plan (T-HUB-022 s15)

## 1. Call-sites Audit Table

| Function | File / Line | Trigger Condition | Current Behavior | Sunset Plan |
|---|---|---|---|---|
| `repair_index_mirror` | `loop/context_loop.py:1128` | Pre-step prepare execution if `armed_decompose` is set | Syncs `index.yaml` step status back to legacy `index.md` | Legacy-only fallback. Sunset in `s16` or retain as log-only warning under `PROJECT_LOOP_REPAIR_LEGACY=0`. |
| `repair_index_mirror` | `loop/context_loop.py:1566` | Post-step check_after execution if `armed_decompose` is set | Syncs `index.yaml` step status back to legacy `index.md` | Legacy-only fallback. Sunset in `s16`. |
| `repair_fingerprint_stall` | `loop/context_loop.py:1596` | Post-step check_after when `fp_now == before` (agent exited without activeContext change) | Repairs stall state if implement shard checkpoints/files exist | Sunset in `s16` or convert to log-only drift counter increment. |
| `repair_finish_desync` | `.claude/hooks/epic/core.py:2568` | Invoked via `validate_finish_integrity_with_repair` during finish check | Repairs desync between `index.yaml` and active context / implement state | Sunset in `s16` / log-only. |

## 2. Drift Observability Counters Audit

When running standard loop iterations without forced legacy parameters:
- `index_mirror_repair`: **0** (near-zero, incremented only when legacy `index.md` desyncs from `index.yaml`)
- `fingerprint_stall_repair`: **0** (near-zero, incremented only when agent stalls)
- `gate_verdict_regex_fallback`: **0** (near-zero, regex fallback during verdict parsing)

State diagnostics counters tracked via `increment_drift_counter`:
- `gate_verdict_regex_fallback`
- `index_mirror_repair`
- `fingerprint_stall_repair`
- `finish_desync_repair`

All remain zero during normal runtime operations under schema v1.
