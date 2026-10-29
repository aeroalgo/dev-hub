# Epic QA shard — `epic-qa/v1`

Канон: `epic-step.yaml` → `memory-bank/{back|front|integration}/qa/<epic>/qa-YYYYMMDD-<slug>.yaml`  
**FORBIDDEN:** параллельно писать `qa.yaml` с тем же отчётом (один файл на прогон). `qa.yaml` = только mb-scaffold stub.

- `verdict` — pass | fail | blocked (согласован с Handoff)
- `scope[]`, `checks[]` — обязательны
- `coverage_map[]` — literal AC/BN → browser/API scenario → evidence; every applicable row is covered
- `review`, `test_audit`, `browser` — explicit review/test-quality/browser evidence (or `status: skip` with reason)
- `retro` — four short answers: missed defect, redundant gate, flaky test, next-cycle change
- `review` and `test_audit` are the built-in QA subpasses with gstack-compatible
  aliases `/review` and `/test-audit`; they are not separate loop phases or
  user commands.
- Brownfield replacement — `sunset_inventory_scan` and `sot_enforce_scan` are
  filled in this same QA artifact; there is no separate review phase or file.
- `fix_plan[]` — обязателен при fail/blocked; `finish_qa` создаёт/мерджит `memory-bank/{role}/bugfix/<epic>/bugfix-queue.yaml`

Validate: `python3 .claude/hooks/epic_resolve.py validate-step --path <shard.yaml>`

Очередь `epic-bugfix-queue/v1` — machine SoT статусов BUGFIX; `bugfix-*.md` не является источником прогресса.

Legacy `review.md` — human outline only; FINISH artifact = yaml.
