# dev-hub

Хаб разработки: workflow rules, skills, Claude hooks, loop.  
Продуктовый код и `memory-bank/` живут в отдельных репозиториях (например `../job-autopilot`).

## Layout

```
dev-hub/
  .cursor/rules · templates   # Cursor workflows (BACK PLAN, …)
  .claude/                    # hooks, agents, project.env, skills
  .agents/skills/             # общие skills (также ~/.agents → сюда)
  loop/                       # автоцикл
  runtime/<project>/          # state loop per product
  projects/<slug>/            # optional project.env.local overrides
  bin/loop                    # wrapper
  workspaces/                 # optional; multi-root НЕ рекомендуем (путает memory-bank)
  CLAUDE.md
```

## Подключение проекта

1. Открой в Cursor **только папку продукта** (`../job-autopilot`), не multi-root с hub
2. Cursor plugin mount: `~/.cursor/plugins/local/dev-hub` → этот каталог
3. `~/.agents` → symlink на `dev-hub/.agents`

В продуктовом репо после `hub-link` — symlinks на rules/skills; `memory-bank/` только свой.

## Cursor (режимы / skills)

```bash
make hub-link          # symlinks .cursor/rules, .agents, CLAUDE.md → hub
# затем: Developer: Reload Window
```

После `hub-link` в продукте видны `BACK IMPLEMENT` и skills.  
**Не** открывай multi-root product+hub: два `memory-bank/` путают агентов.

## Loop

Из корня **продукта**:

```bash
make loop ARGS="gpt"
make loop ARGS="decompose-T-013 gpt"
make loop-epic EPIC=decompose-T-013 MODEL=gpt
make loop-status
```

Или напрямую:

```bash
/home/aero/PyProject/dev-hub/bin/loop /home/aero/PyProject/job-autopilot gpt
```

- `DEV_HUB` / `HUB_ROOT` — этот каталог (tooling)
- `PROJECT_ROOT` — продукт с `memory-bank/` (для Make = `CURDIR`)
- runtime → `runtime/<basename(PROJECT_ROOT)>/epic/`
- Claude стартует с **cwd = hub** (видит `.claude/agents`, hooks, settings)  
  и получает продукт через `--add-dir $PROJECT_ROOT`.  
  Symlink `.claude` в продукт **не нужен**.

Перенос в другой репо: скопируй корневой `Makefile` + при необходимости `.dev-hub`  
(одна строка — путь к хабу). Общие цели — `dev-hub/make/product.mk`.

### DSH Runtime (opt-in)

> **Note:** DSH Runtime is currently in developer preview and is not the production default.

Для запуска с DSH runtime используйте переменную окружения `EPIC_RUNTIME=dsh`:

```bash
EPIC_RUNTIME=dsh /home/aero/PyProject/dev-hub/bin/loop /home/aero/PyProject/job-autopilot gpt
```

Подробности и инструкции по пилоту: [`docs/runbooks/dsh-loop-pilot.md`](docs/runbooks/dsh-loop-pilot.md) и [`dsh/README.md`](dsh/README.md).

## Новый продукт

1. Открой папку продукта в Cursor; `make hub-link` из корня продукта
2. Запускай `bin/loop /path/to/product …` или `make loop` из продукта
3. При необходимости: `projects/<slug>/project.env.local`

## Dashboard

Harness metrics dashboard генерирует HTML и JSON отчёты о метриках исполнения loop, инцидентах и активных эпиках.

### Usage (CLI)

Сгенерировать HTML/JSON отчёт в `runtime/<project>/reports/`:

```bash
python -m loop.context_loop dashboard-render [--days DAYS] [--format {html,json,both}]
```

Параметры:
- `--days`: Окно агрегации метрик в днях (по умолчанию `7`).
- `--format`: Формат отчёта — `html` (по умолчанию), `json` или `both`.

### Environment Variables

- `EPIC_DASHBOARD_HALT_WARN_RATE`: Порог коэффициента остановки loop (halt rate) для проверки `loop doctor`. По умолчанию `0.50` (50%). Если текущий halt rate превышает этот порог, `loop doctor` выдаёт предупреждение (warn).

## Команды ролей

`BACK PLAN`, `BACK IMPLEMENT`, … распознаются через rules/skills хаба  
(workspace + plugin), не через файлы в product git.
