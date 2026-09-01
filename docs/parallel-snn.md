# Parallel SNN Execution (`EPIC_PARALLEL_SNN`)

`docs/parallel-snn.md` documents the design, configuration, and merge policy for executing independent `sNN` shards in parallel using isolated git worktrees.

---

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `EPIC_PARALLEL_SNN` | `0` | Opt-in flag for parallel wave execution. Set to `1` to enable parallel wave spawning. |
| `EPIC_PARALLEL_MAX` | `2` | Maximum number of non-overlapping `sNN` steps to spawn concurrently in separate worktrees. |

---

## Merge Policy (v1)

1. **Pre-parallel Commit Requirement**: Operators must ensure clean atomic commits per `sNN` prior to running parallel waves.
2. **Conflict Resolution**: Steps with file overlap automatically trigger sequential fallback during wave computation. If a git merge conflict arises post-execution, manual resolution is required.

---

## Integration Point

- **`arm_phase` (T-HUB-029)**: The parallel orchestrator checks for `EPIC_PARALLEL_SNN=1` during the `arm_phase` transition in `loop.sh` when `armed_step=IMPLEMENT`. When armed, it evaluates the ready wave via `compute_ready_wave`, filters overlapping file shards via `file_overlap_check`, and spawns parallel sub-loop executions.
