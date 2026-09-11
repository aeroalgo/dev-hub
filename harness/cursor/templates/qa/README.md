# Epic QA shard — `epic-qa/v1`

Канон: `epic-step.yaml` → `memory-bank/{back|front|integration}/qa/<epic>/qa-YYYYMMDD-<slug>.yaml`  
**FORBIDDEN:** параллельно писать `qa.yaml` с тем же отчётом (один файл на прогон). `qa.yaml` = только mb-scaffold stub.

- `verdict` — pass | fail | blocked (согласован с Handoff)
- `scope[]`, `checks[]` — обязательны
- `fix_plan[]` — обязателен при fail/blocked; `finish_qa` создаёт/мерджит `memory-bank/{role}/bugfix/<epic>/bugfix-queue.yaml`

Validate: `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`

Очередь `epic-bugfix-queue/v1` — machine SoT статусов BUGFIX; `bugfix-*.md` не является источником прогресса.

Legacy `review.md` — human outline only; FINISH artifact = yaml.
