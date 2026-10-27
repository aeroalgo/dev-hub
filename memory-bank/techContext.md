# Tech context — dev-hub

## Языки / рантайм

- Python 3 — `loop/`, `.claude/hooks/`, `.cursor/hooks/`, часть тестов
- Bash — `bin/loop`, `bin/hub-link`, `bin/hub-unlink`, `loop/loop.sh`
- Markdown / MDC — `.cursor/rules`, `.claude/rules`, skills

## Зависимости

- Системный / внешний `python3`; у хаба есть собственный `.venv` (pytest для loop)
- Hub deps install: `.venv/bin/pip install -r requirements-hub.txt` (pydantic-ai + pydantic>=2)
- Claude Code CLI (сессии loop)
- Cursor IDE (rules / hooks)

## Тесты (hub)

- Тесты loop: из `dev-hub/` → `bin/pytest loop/tests/ -q --tb=short` (300s встроен в wrapper)
- Альтернатива: `timeout 300s .venv/bin/pytest …`
- Не из product venv; hub имеет собственный `.venv` с pytest
- Per-item timeout: `pytest-timeout` в `requirements-dev.txt`, `timeout = 300` в `pytest.ini`
- Targeted T-HUB-003: `-k 'check_after or decide_after_action or last_session or halt'`
- Targeted T-HUB-108: `bin/pytest loop/tests/test_board_projection* -q --tb=short`

## Persistence

- `runtime/<product-slug>/epic/` — `state.json`, checkpoint, locks, session logs (телеметрия runner)
- `runtime/<product-slug>/spawn-gate/` — gate JSON
- Product artifacts — **не** в этом репо (`PROJECT_ROOT/memory-bank/`)
- Доменной SQL/ORM в хабе **нет**

## Product constitution bootstrap

- Команда инициализации/bootstrap constitution: `python3 .claude/hooks/epic_resolve.py seed-constitution --cwd <path>`
- Для L2+ эпиков создаёт `memory-bank/constitution.md` из seed шаблона, если он отсутствует.

## Конфиги

- `.claude/project.env` — канон runtime/permission (loop)
- `.claude/project.env.local` — локальные overrides
- `projects/<slug>/project.env.local` — опциональные per-product overrides (каталог пуст на момент VAN)

## Асинхронность

- Loop: последовательные сессии агента + bounded timeout/retry (`EPIC_*` в project.env)
- DAG `loop-dag/v2`: dependency-ready nodes **по одному**, без distributed lock

## Epic kinds и Security pipeline

- Epic kinds: `feature` (default), `refactor`, `security` (`Cursor.kind`)
- Пути plan/index/implement/security: layout под `memory-bank/<role>/{,refactor/,security/}plan/<id>/`
- Валидация execute SECURITY: `schema: epic-security/v1` (`loop.kernel.security_schema`)
- Gate agent: `verify-security` (`harness/agents/verify-security.md`)
- Lifecycle `security`: `DECOMPOSE` -> `SECURITY` (@aNN*) -> `DONE` (skip ANALYZE/AUDIT/QA/CONTEXT_SYNC)

## Board projection (T-HUB-108)

- Конфигурация: `.loop/board-projection.yaml` (`provider: "bitrix24" | "plane" | "none"`).
- Sidecar mapping: `.loop/board-epic-map.yaml` (`schema: board-epic-map/v1`) — связь `epic_id` ↔ `external_id` с жестким scope провайдера.
- Архитектура: Protocol `BoardProjectionAdapter` + registry провайдеров (`loop/board_projection/`).
- Адаптеры:
  - `Bitrix24Adapter`: inbound webhook REST (`tasks.task.add`, `task.stages.movetask`), `stage_map` по фазам.
  - `PlaneAdapter`: REST API key (`/api/v1/workspaces/.../work-items/`, PATCH state), `state_map` по фазам.
- Интеграция в loop: post-finish hook в `loop/kernel/engine.py` после фиксации курсора.
- Обработка ошибок: soft-fail (ошибки REST логируются и пишутся в sidecar как `sync_error`, не откатывая курсор фаз loop).
- Catch-up CLI: `bin/loop.py board-sync --project <path>` (догон и повторная попытка синхронизации незавершённых проекций).
