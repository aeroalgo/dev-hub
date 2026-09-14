## Epic

### Outcome

A worker cannot turn its own edits into a passing verification by writing capability evidence files. Successful verification remains an independently produced fact at the tool boundary.

### In

- PreTool Write/Edit deny for capability execution evidence paths under memory-bank role trees.
- Alignment of finish/read rejection with executor provenance (producer stamp owned elsewhere; this epic owns deny + non-authoritative read enforcement).

### Out

- Managed capability_checks requirement / hub fallback policy (separate follow-up).
- Incident auto-clear on loop start (separate follow-up).
- Gate receipt schema redesign already delivered by the parent integrity epic.

### Done when

1. An agent Write/Edit to a capability evidence sidecar is denied with an actionable reason.
2. Finish does not accept evidence lacking executor provenance as a pass.

### Forbidden after

Mutable evidence as authority, silent allow of execution-path writes, dual soft deny.

### Chat decisions

- Spawned as REPLAN follow-up; parent Epic prompt is linked from plan header Parent-prompt.
- foreign_dirty FAIL→PASS promote left in backlog unless proven to forge worker PASS.

---

## Covering

n/a — single epic
