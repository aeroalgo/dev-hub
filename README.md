# dev-hub

Единый tooling-хаб для ролевых workflow (`BACK PLAN`, `FRONT IMPLEMENT`, `INTEG GAP`, …), skills, Claude/Cursor/Codex hooks и автоцикла эпиков (`loop/`).

**Важно:** dev-hub — это **не** продуктовый репозиторий. Код приложения и `memory-bank/` артефакты живут в отдельном репо (продукте). Хаб подключается к продукту через `hub-link` (symlinks) и CLI.

Краткий install-runbook: [`docs/install.md`](docs/install.md).

---

## Требования

| Компонент | Версия / зачем |
|-----------|----------------|
| **Python** | **3.12+** (канон; код loop/hooks — 3.10+) |
| **git** | loop, hub-link |
| **jq** | shell-скрипты security-auditor |
| **Claude CLI** и/или **Codex CLI** | runtime для `bin/loop.py` |

### Окружение для разработки и тестов хаба

Из корня **dev-hub** (не продукта):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # при необходимости подправьте LOOP_* / EPIC_RUNTIME
bin/pytest
```

`requirements-dev.txt` подтягивает `requirements-hub.txt` (pydantic, httpx, pydantic-ai, …) и pytest/PyYAML.

По умолчанию тесты идут параллельно через `pytest-xdist` (`-n 4`, override: `PYTEST_WORKERS` или `-n`):

```bash
bin/pytest -q --tb=line
PYTEST_WORKERS=8 bin/pytest loop/tests -q
```

Для тестов, которые меняют checkout, отключайте параллелизм: `-n 0`.

---

## Рекомендуемая структура на диске

```
~/PyProject/
├── dev-hub/              ← этот репозиторий (tooling, harness, loop)
├── my-product/           ← ваш продукт (код + memory-bank/)
│   ├── Makefile          ← тонкий wrapper → dev-hub/make/product.mk
│   ├── .dev-hub          ← одна строка: ../dev-hub  (создаёт hub-link)
│   ├── dev-hub.project.yaml  ← опционально: targets / workflow_pack
│   ├── memory-bank/      ← артефакты workflow ТОЛЬКО продукта
│   ├── harness/          ← symlink → dev-hub/harness  (alongside)
│   ├── .cursor/rules …   ← symlinks на harness/cursor/… (после hub-link)
│   └── AGENTS.md · CLAUDE.md  ← symlinks → dev-hub
└── another-product/
```

| Репозиторий | Что внутри | Куда пишут агенты |
|-------------|-----------|-------------------|
| **dev-hub** | rules, skills, hooks, loop, runtime state | `dev-hub/memory-bank/` — **только** hub-эпики `T-HUB-*` |
| **продукт** | application code + `memory-bank/` | `my-product/memory-bank/` — все product-эпики |

Хаб может лежать **где угодно**. Главное — путь через `.dev-hub` / `DEV_HUB` / соседний `../dev-hub`.

---

## Поддерживаемые агенты

| Runtime | Loop | Prerequisites | Runbook |
|---------|------|---------------|---------|
| **claude** | default | Claude CLI + auth | [`loop/README.md`](loop/README.md) |
| **codex** | opt-in (`EPIC_RUNTIME=codex` / `--runtime codex`) | Codex CLI ≥ 0.152, `codex login`, `bin/runtime-sync` | [`docs/runbooks/codex-loop-pilot.md`](docs/runbooks/codex-loop-pilot.md) |

Подключение продукта одинаковое: `make hub-link`, открыть **только** папку продукта.

---

## Быстрый старт: подключить продукт

### 1. Клонировать dev-hub

```bash
git clone <url-dev-hub> ~/PyProject/dev-hub
cd ~/PyProject/dev-hub
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

### 2. Подготовить продукт

```bash
mkdir -p ~/PyProject/my-product && cd ~/PyProject/my-product
git init   # если новый репо
cp ~/PyProject/dev-hub/make/Makefile.product.example ./Makefile
# опционально: шаблон targets
cp ~/PyProject/dev-hub/harness/templates/dev-hub.project.yaml ./dev-hub.project.yaml
```

### 3. Подключить harness (`hub-link`)

Из **корня продукта**:

```bash
make hub-link
# эквивалент (alongside + skills — то, что делает Make):
~/PyProject/dev-hub/bin/hub-link --with-skills ~/PyProject/my-product
```

**Режимы `hub-link`:**

| Mode | Когда | Что делает |
|------|--------|------------|
| **`alongside`** (default) | внешний продукт | symlink `harness/`, `.cursor/rules`→`harness/cursor/rules`, Claude/Codex overlays, `AGENTS.md`/`CLAUDE.md`, пишет `.dev-hub`; `--with-skills` → `.agents/skills` |
| **`full`** | dogfood / полная реплика | symlink `.cursor/rules`, `.agents/skills`, `.claude/*`, `settings.json` напрямую на shell хаба |

```bash
# явный alongside
./bin/hub-link --mode alongside [--with-skills] /path/to/product
# полная реплика
./bin/hub-link --mode full /path/to/product
# dry-run
./bin/hub-link --dry-run /path/to/product
```

`make hub-link` всегда вызывает alongside **с** `--with-skills`.

Подробности layout: [`harness/README.md`](harness/README.md).

Конфигурация targets — только корневой **`dev-hub.project.yaml`** (`schema: dev-hub-project/v1`). Устаревшие `project.yaml` / `.dev-hub/project.yaml` **не** читаются. Файл `.dev-hub` — **только** однострочный указатель пути к хабу, не каталог конфигов.

Локальные `.claude/runtime/` и `.claude/worktrees/` остаются в продукте (не symlink на хаб).

### 4. memory-bank продукта

```bash
mkdir -p memory-bank
# В Cursor: BACK VAN
```

Эпики `T-HUB-*` — только в `dev-hub/memory-bank/`.

### 5. Открыть продукт в Cursor

```bash
cursor ~/PyProject/my-product
```

После `hub-link`: **Developer → Reload Window**.

**Не** открывайте multi-root «продукт + dev-hub» — два `memory-bank/` путают агентов.

### 6. (Опционально) глобальные skills / plugin

```bash
ln -sfn ~/PyProject/dev-hub/.agents ~/.agents
mkdir -p ~/.cursor/plugins/local
ln -sfn ~/PyProject/dev-hub ~/.cursor/plugins/local/dev-hub
```

Для day-to-day достаточно `hub-link` + папка продукта.

---

## Makefile в продукте

В git продукта — **только тонкий** `Makefile`. Логика — в `dev-hub/make/product.mk` (include).

Шаблон: [`make/Makefile.product.example`](make/Makefile.product.example).

### Цели `product.mk`

| Команда | Назначение |
|---------|------------|
| `make hub-link` | alongside + `--with-skills` |
| `make hub-unlink` | снять installer-owned links |
| `make hub-info` | `DEV_HUB`, links |
| `make loop ARGS="codex\|claude <epic> <model> [effort]"` | обёртка над `bin/loop.py run` |
| `make cursor-workspace` | напоминание: открывать только продукт |
| `make deploy` / `deploy-info` | см. `make/deploy.mk` + `.deploy.env` |

Примеры:

```bash
make hub-info
make hub-link
make loop ARGS="codex T-054-skyro-quality-dashboard-ui gpt-5.6-luna-max high"
python3 "$DEV_HUB/bin/loop.py" status --project "$PWD" --json
```

Переопределить хаб на один запуск: `DEV_HUB=/other/path/dev-hub make hub-info`.

Свои цели (`test`, `run`, …) — **после** `include $(DEV_HUB)/make/product.mk`. Не переопределяйте `hub-link` / `loop`.

---

## Как продукт находит хаб (`DEV_HUB`)

Порядок:

1. env `DEV_HUB=/abs/path/to/dev-hub`
2. файл `.dev-hub` (одна строка — относительный или абсолютный путь)
3. соседний `../dev-hub` (если есть `../dev-hub/bin/loop.py`)

```bash
echo '../dev-hub' > .dev-hub
# или
echo '/home/aero/PyProject/dev-hub' > .dev-hub
make hub-info
```

`.dev-hub` можно коммитить — это не секрет.

---

## Loop — автоцикл эпиков

Канон: [`loop/README.md`](loop/README.md). Запуск **всегда** с `--project` (каталог продукта).

```bash
# из продукта
python3 "$DEV_HUB/bin/loop.py" run \
  --project "$PWD" \
  --epic T-054-skyro-quality-dashboard-ui \
  --runtime codex \
  --model gpt-5.6-luna-max \
  --role front

python3 "$DEV_HUB/bin/loop.py" status --project "$PWD" --json
python3 "$DEV_HUB/bin/loop.py" doctor --project "$PWD" --json
```

Или через Make:

```bash
make loop ARGS="codex T-054-skyro-quality-dashboard-ui gpt-5.6-luna-max"
```

Настройки — корневой **`.env`** хаба (`LoopSettings`). Шаблон: [`.env.example`](.env.example). Старый `.claude/project.env` не читается.

| Переменная | Значение |
|-----------|----------|
| `HUB_ROOT` / `DEV_HUB` | каталог dev-hub |
| `PROJECT_ROOT` | продукт с `memory-bank/` |
| Loop state | `dev-hub/runtime/<basename(PROJECT_ROOT)>/epic/` |

Claude-сессия loop: cwd = hub, продукт через `--add-dir`. Для Cursor достаточно `hub-link`; отдельный ручной symlink `.claude` → hub не нужен.

---

## Перенос на другую машину

1. Клонировать dev-hub + продукт; `pip install -r requirements-dev.txt`; `cp .env.example .env`
2. В продукте — `Makefile` из example + при необходимости `.dev-hub` / `dev-hub.project.yaml`
3. `make hub-link` → Reload Window

Не копируйте `make/product.mk` в продукт.

---

## Отключение

```bash
make hub-unlink
# или
~/PyProject/dev-hub/bin/hub-unlink [--mode alongside|full] ~/PyProject/my-product
```

По умолчанию режим `alongside` (симметрично link).

---

## Разработка самого dev-hub

- Открывать папку **`dev-hub`**
- `python3 ./bin/loop.py run --project . --epic T-HUB-… --model …`
- Артефакты — в `dev-hub/memory-bank/`
- Не смешивать hub-эпики с product `memory-bank/`
- В корне хаба **не** гонять `hub-link --mode alongside` (harness уже dogfood)

---

## Частые ошибки

| Ошибка | Что делать |
|--------|------------|
| Multi-root product+hub | Открыть **только** продукт |
| Product-эпики в `dev-hub/memory-bank/` | Писать в `$PROJECT_ROOT/memory-bank/` |
| Нет `hub-link` после клона | `make hub-link` + Reload Window |
| `DEV_HUB not found` | `.dev-hub` или соседний `../dev-hub` или `DEV_HUB=` |
| `exists and is not a symlink` | Переименовать локальный файл/каталог, повторить link |
| Ручной symlink `.claude` → hub | Использовать `bin/hub-link` |
| Старый CLI `loop.py PATH EPIC MODEL` | Использовать `run --project … --epic … --model …` |

---

## Dashboard

```bash
python3 -m loop.context_loop dashboard-render [--days 7] [--format html|json|both]
```

Отчёты: `runtime/<project>/reports/`.  
`EPIC_DASHBOARD_HALT_WARN_RATE` (default `0.50`) — порог для `loop doctor`.

---

## Layout (справочно)

```
dev-hub/
  harness/                 # SoT: rules, skills, agents, hooks policy
  .cursor/ · .claude/ · .agents/   # thin symlink shells → harness
  .env                     # local LoopSettings (gitignored)
  loop/                    # single-cursor kernel
  runtime/<project>/       # loop state per product
  bin/loop.py · hub-link · hub-unlink
  make/product.mk · Makefile.product.example
  docs/install.md          # этот install-гайд (кратко)
```

---

## Команды ролей

`BACK PLAN`, `BACK IMPLEMENT`, `FRONT QA`, `INTEG GAP`, `BOARD SYNC`, `PROJECT DOCS`, … — через rules/skills после `hub-link`. В git продукта эти деревья **не** хранятся — только symlinks / router stub.

- Loop: [`loop/README.md`](loop/README.md), [`loop/WORKFLOW.md`](loop/WORKFLOW.md)
- Install: [`docs/install.md`](docs/install.md)
- Harness modes: [`harness/README.md`](harness/README.md)
- Codex pilot: [`docs/runbooks/codex-loop-pilot.md`](docs/runbooks/codex-loop-pilot.md)
