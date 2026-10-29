# Epic QA shard — `epic-qa/v1`

Канон: `epic-step.yaml` → `memory-bank/{back|front|app|integration}/qa/<epic>/qa-YYYYMMDD-<slug>.yaml`
**FORBIDDEN:** параллельно писать `qa.yaml` с тем же отчётом (один файл на прогон). `qa.yaml` = только mb-scaffold stub.

- `verdict` — pass | fail | blocked (согласован с Handoff)
- `scope[]`, `checks[]` — обязательны
- `coverage_map[]` — literal AC/BN → browser/API scenario → evidence; every applicable row is covered
- `test_plan` — scope-driven selection from `test-catalog.yaml`; every catalog item is selected, marked `not_applicable` with a reason, or marked `not_run` with a next action
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

## Scope-driven test catalog

`test-catalog.yaml` is a universal list of named test obligations, not a list of
hard-coded commands. QA derives the applicable set from the current implement
shards (`files`, `tests`, `integration_check`, `wire_complete`), the product
contract, the diff, and prior blockers.

- `full` selects every applicable catalog item.
- `diff_aware` selects changed and adjacent behavior plus the risk categories
  signaled by the scope.
- `regression` selects the full applicable set and all prior failed obligations.
- Every catalog item must appear in `selected`, `not_applicable` with a reason,
  or `not_run` with a next action. Omission is not a skip.
- A selected item without executable evidence is a gap. If the implement shard
  did not provide the needed test, QA records the missing obligation; it is not
  silently converted into a PASS.

The catalog intentionally contains no hosts, ports, URLs, credentials, or
project-specific commands. Those details are supplied by the implement shard,
stack profile, and named QA lanes.
