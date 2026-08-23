# Epic loop — fresh session per step

Автоцикл: **`./loop/loop.sh`**  
Канон переходов: `memory-bank/activeContext.md` + `decompose/index.yaml`; курсор = `memory-bank/activeContext.md`

Один чат = один atomic шаг. Агент читает context и пишет следующий Handoff.

**Стоп:** `EPIC_DONE` | `BLOCKED:` | `NEED_HUMAN:`  
**Не стоп:** `GAPS:` / `**GAPS:**` (deferred scope / заметки — пиши `Отложено:`)

## Запуск

**Снаружи** Claude-сессии (отдельный терминал). Агент внутри сессии **не** вызывает runner.

```bash
./loop/loop.sh gpt
./loop/loop.sh decompose-v1-portal gpt
./loop/loop.sh -m gpt --max 20
./loop/loop.sh --status
```

FORBIDDEN argv (удалены / не поддерживаются): `--track`, `--id`, `--gap`, `--resume-implement`.
Нет отдельных `epic-loop.sh` / `program-loop.sh` — только `./loop/loop.sh`.

`decompose-<id>` — ручной switch эпика: **overwrite** `activeContext` из index (первый pending/active/blocked). Без аргумента — текущий activeContext.

## Env

All runtime limits are bounded and non-secret. `.claude/project.env` is the checkout canon; `.claude/project.env.local` may override it according to the runner's source precedence. Do not create or synchronize values to a hypothetical example file. Invalid values fail closed with `invalid_runtime_config`; zero/unlimited mode is not supported.

| Var | Default / meaning |
|-----|------------------|
| `EPIC_LOOP` | set by script |
| `CLAUDE_BIN` | auto |
| `EPIC_PERMISSION_MODE` | this checkout uses `bypassPermissions`, loaded from `.claude/project.env` |
| `EPIC_MAX` / `--max` | `40` |
| `EPIC_SESSION_TIMEOUT_SEC` | `3600` |
| `EPIC_SESSION_KILL_GRACE_SEC` | `30` |
| `EPIC_TRANSIENT_RETRY_MAX` | `30` |
| `EPIC_DEGRADED_MAX` | `3` |
| `EPIC_STATUS_HEARTBEAT_SEC` | empty = disabled |

Status output is secret-free and exposes effective values plus their sources; it must not expose prompts, tokens or secret values.

## Permissions (scope = repo)

Loop держит effective `--permission-mode bypassPermissions`, загруженный из `.claude/project.env`; prompt не используется.

Канон allow/deny: `.claude/settings.json` → `permissions`.

- Файлы: только `Edit(/…)` / `Read(/…)` (якорь = корень репо). **`Write(path)` не работает** — Claude Code смотрит только `Edit(path)`.
- Scope: `Edit(/**)` + `Read(/**)` = весь репозиторий; вне allow + `dontAsk` → deny. Не добавлять `Edit(//**)` в deny — перекроет абсолютные пути внутри репо.
- Bash/Agent/Skill — allow; catastrophic `rm -rf /|~` — deny.
- Не ставить `Write(**)` / `Edit(**)` — path-check их не матчит (e19 Write deny).

## State and recovery

- `activeContext.md` + decompose index + implement step are the transition source of truth; runner status is evidence, not a replacement for those artifacts.
- A durable checkpoint owns the cursor and `resume_from_step`. Lifecycle checkpoints preserve `pending`, `active`, `completed`, `BLOCKED` and `NEED_HUMAN`; blocked states require explicit validated resume.
- Canon epic runtime dir: `HUB_ROOT/runtime/<slug>/epic/` (same as `loop.sh` `STATE_DIR` / `epic_paths.epic_dir` when `HUB_ROOT`/`DEV_HUB` set). It contains `next-prompt.txt`, `session-*.log`, `last-session.json` and `state.json`. `state.json` mirrors checkpoint telemetry for status/stop-gate and never owns the durable cursor; agents must not edit it. Checkpoint/index conflicts halt fail-closed.
- Legacy path (product cwd, no hub env): `PROJECT_ROOT/.claude/runtime/epic/` — fallback only in `epic_paths.epic_dir` when hub is unset; docs and operators treat hub `runtime/<slug>/epic/` as primary.
- After timeout or process death, inspect `<hub>/runtime/<slug>/epic/last-session.json`, preserve event evidence and resume only from the validated checkpoint. A transient retry cap is bounded and does not reset to the first pending step. Never auto-delete product runtime dirs.

## Production rollout and rollback

- **Phase A — observe:** collect bounded status and v1 compatibility diagnostics.
- **Phase B — shadow:** validate `loop-dag/v2` dependency/order/checkpoint behavior without scheduling.
- **Phase C — canary:** run one dependency chain sequentially under timeout, kill-grace, retry and degraded caps.
- **Phase D — expand:** add chains after restart-after-timeout, process-death and `BLOCKED`/`NEED_HUMAN` resume evidence.
- **Phase E — enforce:** reject malformed sources and checkpoint/index conflicts fail-closed.
- **Rollback:** stop new scheduling, preserve event/checkpoint evidence, restore the last validated cursor or `resume_from_step`, and label any manual fallback. Never delete `state.json`, reset to first pending, or treat manual regex recovery as autonomous projection authority.

T-034 policy is a boundary for this loop and does not authorize agent state mutation. `GAP_FANOUT` is manual-only in this checkout; the scheduler is sequential, has no parallel mode, and has a one-checkout limitation (one checkout).

## FINISH-последовательность (IMPLEMENT — обязательно)

```
seed-implement (status: in_progress, cp=pending) →
flush-checkpoint после каждого зелёного cp →
suite → evidence (done/files/tests; status остаётся in_progress) →
python3 .claude/hooks/epic_resolve.py validate-step --path <shard> →
Handoff в activeContext.md →
@verify →
VERDICT: PASS →
python3 .claude/hooks/epic_resolve.py finalize-step --decompose <id> --step sNN →
проверить JSON-ответ: `"ok": true` (implement+index+log атомарно) →
stop
```

**HARD:** `finalize-step` вызывается агентом **только после `VERDICT: PASS`** — без исключений.  
**HARD:** `status: completed` в implement пишет **только** `finalize-step` (вместе с index); агент не ставит completed руками.  
**HARD:** агент **не** пишет `tasks.md` / `tasks/log` на IMPLEMENT sNN — это делает `finalize-step`.  
**HARD:** stop разрешён только после успешного ответа `finalize-step` с `"ok": true`; намерение вызвать команду не считается завершением transition.  
**HARD:** если `@verify` не вернул `VERDICT:` строку → один retry `@verify`; если снова нет `VERDICT:` → `NEED_HUMAN: verify_no_verdict`.  
**HARD:** пропустить `finalize-step` после PASS = FAIL.  
**HARD:** `BLOCKED: verify_no_verdict` запрещён (loop может автоочистить) — только `NEED_HUMAN:`.
**HARD:** `mark_index_missing` на prepare/check_after → auto-rollback implement `completed`→`in_progress` (без auto-mark index); затем сессия продолжается на том же шаге.

## Не делать

- Не крутить следующий sNN/eNN в той же сессии
- Не `--continue` / `-c` в loop
- Не вызывать `epic_resolve` `after|resolve|arm|halt|complete|record-session`
- Не вызывать `validate-step` / `mark-index-status` **до** `VERDICT: PASS` от `@verify`
- Не писать `tasks.md` / `tasks/log` на IMPLEMENT sNN (только `finalize-step`)
- Не писать `BLOCKED: verify_no_verdict` — только `NEED_HUMAN: verify_no_verdict` после исчерпания retry
