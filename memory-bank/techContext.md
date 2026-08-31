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

- Тесты loop: из `dev-hub/` → `.venv/bin/pytest loop/tests/ -q --tb=short`
- Не из product venv; hub имеет собственный `.venv` с pytest
- Внешний timeout: `timeout 300s` (см. `test-timeout.mdc`)
- Targeted T-HUB-003: `-k 'check_after or decide_after_action or last_session or halt'`

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
