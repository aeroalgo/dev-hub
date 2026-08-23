# Epic SECURITY execute shard — `epic-security/v1`

Канон: `epic-step.yaml` → `memory-bank/{role}/security/implement/implement-<id>/aNN-<slug>.yaml`

S one-shot без yaml: `security/security-audit-YYYYMMDD-<slug>.md`

FINISH: `status: completed`, `findings[]` (минимум одна строка), checkpoints `done`. `code_changed: no`.

Validate: `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`

Decompose spec: `step.md` (plan slice). Implement result: `epic-step.yaml`.
