# Epic REFACTOR implement shard — `epic-refactor/v1`

Канон: `epic-step.yaml` → `memory-bank/{role}/refactor/implement/implement-<id>/rNN-<slug>.yaml`

Один `rNN` за сессию. FINISH: `status: completed`, все checkpoints `done`, `behavior_freeze`, `done`, `files`, `tests`.

Validate: `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`
