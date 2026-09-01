# dev-hub

Единый tooling-хаб для ролевых workflow (`BACK PLAN`, `FRONT IMPLEMENT`, `INTEG GAP`, …), skills, Claude/Cursor hooks и автоцикла эпиков (`loop/`).

**Важно:** dev-hub — это **не** продуктовый репозиторий. Код приложения и `memory-bank/` артефакты живут в отдельном репо (продукте). Хаб только подключается к продукту через symlinks и CLI.

---

## Рекомендуемая структура на диске

Самый простой и предсказуемый вариант — **соседние папки** в одном родителе:

```
~/PyProject/
├── dev-hub/              ← этот репозиторий (tooling, rules, loop)
├── my-product/           ← ваш продукт (код + memory-bank/)
│   ├── Makefile          ← тонкий wrapper → dev-hub/make/product.mk
│   ├── .dev-hub          ← одна строка: ../dev-hub  (создаёт hub-link)
│   ├── memory-bank/      ← артефакты workflow ТОЛЬКО продукта
│   ├── .cursor/rules     ← symlink → dev-hub/.cursor/rules
│   ├── .agents           ← symlink → dev-hub/.agents
│   └── CLAUDE.md         ← symlink → dev-hub/CLAUDE.md
└── another-product/
```

| Репозиторий | Что внутри | Куда пишут агенты |
|-------------|-----------|-------------------|
| **dev-hub** | rules, skills, hooks, loop, runtime state | `dev-hub/memory-bank/` — **только** hub-эпики `T-HUB-*` |
| **продукт** | application code + `memory-bank/` | `my-product/memory-bank/` — все product-эпики |

Хаб может лежать **где угодно** — не обязательно рядом. Главное, чтобы продукт знал путь к нему (см. [Как продукт находит хаб](#как-продукт-находит-хаб-dev_hub)).

---

## Быстрый старт: подключить новый продукт

### 1. Клонировать / положить dev-hub

```bash
git clone <url-dev-hub> ~/PyProject/dev-hub
```

Рядом создайте или откройте папку продукта:

```bash
mkdir -p ~/PyProject/my-product
cd ~/PyProject/my-product
git init   # если новый реpo
```

### 2. Добавить Makefile в продукт

Скопируйте шаблон из хаба:

```bash
cp ~/PyProject/dev-hub/make/Makefile.product.example ~/PyProject/my-product/Makefile
```

Makefile сам ищет хаб в порядке: файл `.dev-hub` → соседний `../dev-hub` → переменная `DEV_HUB`.

Подробнее: [Makefile в продукте](#makefile-в-продукте).

### 3. Подключить rules/skills/hooks (hub-link)

Из **корня продукта**:

```bash
cd ~/PyProject/my-product
make hub-link
```

Или напрямую:

```bash
~/PyProject/dev-hub/bin/hub-link ~/PyProject/my-product
```

`hub-link` создаёт symlinks:

| В продукте | → куда указывает |
|-----------|------------------|
| `.cursor/rules`, `.cursor/templates` | `dev-hub/.cursor/…` |
| `.agents` | `dev-hub/.agents` |
| `CLAUDE.md` | `dev-hub/CLAUDE.md` |
| `.claude/agents`, `hooks`, `skills`, `commands`, … | `dev-hub/.claude/…` |
| `.dev-hub` | относительный путь к хабу (для Make) |
| `AGENTS.md` | stub с подсказками для агента |

Локальные каталоги `.claude/runtime/` и `.claude/worktrees/` остаются **в продукте** (не symlink).

### 4. Инициализировать memory-bank продукта

Если `memory-bank/` ещё нет — создайте минимальную структуру и запустите VAN:

```bash
mkdir -p memory-bank
# В Cursor откройте папку продукта и выполните: BACK VAN
```

Эпики hub (`T-HUB-*`) **не** кладите в продукт — они живут в `dev-hub/memory-bank/`.

### 5. Открыть продукт в Cursor

```bash
cursor ~/PyProject/my-product
```

После `hub-link` выполните **Developer → Reload Window**, чтобы подтянулись rules и skills.

**Не открывайте multi-root workspace** «продукт + dev-hub» — два `memory-bank/` путают агентов. Открывайте **только папку продукта**.

### 6. (Опционально) Глобальные skills

Чтобы skills были доступны и вне symlink-дерева:

```bash
ln -sfn ~/PyProject/dev-hub/.agents ~/.agents
```

### 7. (Опционально) Cursor plugin

Альтернатива или дополнение к `hub-link`:

```bash
mkdir -p ~/.cursor/plugins/local
ln -sfn ~/PyProject/dev-hub ~/.cursor/plugins/local/dev-hub
```

Для day-to-day работы достаточно `hub-link` + открытая папка продукта.

---

## Makefile в продукте

В git продукта хранится **только тонкий** `Makefile` (~15 строк). Вся логика hub/loop — в `dev-hub/make/product.mk` (include, не копия).

### Канонический Makefile

Положите в **корень продукта** (`my-product/Makefile`):

```makefile
# Makefile продукта — тонкая обёртка над dev-hub.
#
# Установка:
#   cp /path/to/dev-hub/make/Makefile.product.example ./Makefile
#
# Как хаб находится (по приоритету):
#   1. DEV_HUB=/abs/path/to/dev-hub make …
#   2. файл .dev-hub в корне продукта (одна строка — путь)
#   3. соседний каталог ../dev-hub
#
# Не копируйте make/product.mk в продукт — только include ниже.
# Свои цели (test, migrate, …) добавляйте ПОСЛЕ include.

DEV_HUB ?= $(shell \
  if [ -f .dev-hub ]; then sed -n '1p' .dev-hub | tr -d '[:space:]'; \
  elif [ -x ../dev-hub/bin/loop ]; then printf '%s' "../dev-hub"; \
  else printf ''; fi)

ifeq ($(strip $(DEV_HUB)),)
$(error DEV_HUB not found. Set DEV_HUB=/path/to/dev-hub, create .dev-hub, or use sibling ../dev-hub)
endif

include $(DEV_HUB)/make/product.mk

# --- опционально: product-specific targets ---
#
# .PHONY: test
# test:
# 	.venv/bin/pytest -q
```

Готовый файл в хабе: [`make/Makefile.product.example`](make/Makefile.product.example).

### Файл `.dev-hub` (если хаб не рядом)

Создаётся автоматически при `make hub-link`. Или вручную — **одна строка** в корне продукта:

```bash
# вариант A: хаб соседом (рекомендуется)
echo '../dev-hub' > .dev-hub

# вариант B: хаб где угодно на диске
echo '/home/aero/PyProject/dev-hub' > .dev-hub
```

`.dev-hub` можно коммитить в git продукта — это не секрет, только путь к tooling.

### Цели из product.mk (после include)

| Команда | Назначение |
|---------|------------|
| `make hub-link` | Symlinks rules/skills/hooks из хаба |
| `make hub-unlink` | Убрать symlinks |
| `make hub-info` | Показать `DEV_HUB`, `PROJECT_ROOT`, состояние links |
| `make loop ARGS="gpt"` | Запустить loop (перед этим делает hub-link) |
| `make loop ARGS="decompose-T-013 gpt"` | Loop на конкретный decompose |
| `make loop-epic EPIC=decompose-T-013 MODEL=gpt` | Loop на эпик |
| `make loop-status` | Статус текущего epic/step |
| `make loop-help` | Справка по loop |
| `make cursor-workspace` | Напоминание: открывать только папку продукта |

Примеры:

```bash
make hub-info
make hub-link
make loop ARGS="gpt"
make loop-epic EPIC=decompose-v1-portal MODEL=gpt
make loop-status
```

Переопределить хаб на один запуск:

```bash
DEV_HUB=/other/path/dev-hub make hub-info
```

### Свои цели продукта

Добавляйте **после** `include $(DEV_HUB)/make/product.mk` — не трогайте `product.mk` в хабе:

```makefile
include $(DEV_HUB)/make/product.mk

.PHONY: test run
test:
	.venv/bin/pytest -q
run:
	.venv/bin/uvicorn app.main:app --reload
```

Имена `hub-link`, `loop`, `loop-epic` уже заняты — не переопределяйте их в продукте.

---

## Как продукт находит хаб (DEV_HUB)

Make и loop разрешают путь к хабу **в таком порядке**:

1. **Переменная окружения** `DEV_HUB=/abs/path/to/dev-hub`
2. **Файл `.dev-hub`** в корне продукта (одна строка — относительный или абсолютный путь)
3. **Соседний каталог** `../dev-hub` (если есть `../dev-hub/bin/loop`)

Примеры `.dev-hub`:

```bash
# относительный (рекомендуется при соседнем layout)
echo '../dev-hub' > .dev-hub

# абсолютный (хаб где угодно на диске)
echo '/home/aero/PyProject/dev-hub' > .dev-hub
```

Проверка:

```bash
make hub-info
```

---

## Loop — автоцикл эпиков

Loop **всегда** запускается с указанием продукта (`PROJECT_ROOT`).

Из корня **продукта** (после `hub-link`):

```bash
make loop ARGS="gpt"
make loop ARGS="decompose-T-013 gpt"
make loop-epic EPIC=decompose-T-013 MODEL=gpt
make loop-status
```

Или напрямую из любого места:

```bash
~/PyProject/dev-hub/bin/loop ~/PyProject/my-product gpt
~/PyProject/dev-hub/bin/loop ~/PyProject/my-product decompose-T-013 gpt
```

### Куда пишется runtime

| Переменная | Значение |
|-----------|----------|
| `HUB_ROOT` / `DEV_HUB` | каталог dev-hub (tooling) |
| `PROJECT_ROOT` | каталог продукта с `memory-bank/` |
| Loop state | `dev-hub/runtime/<basename(PROJECT_ROOT)>/epic/` |

Пример: продукт `~/PyProject/my-product` → runtime в `dev-hub/runtime/my-product/epic/`.

### Как работает Claude Code при loop

- **cwd сессии** = dev-hub (видит `.claude/agents`, hooks, settings)
- **продукт** подключается через `--add-dir $PROJECT_ROOT`
- Symlink `.claude` в продукт для loop **не нужен** — достаточно `hub-link` для Cursor и `bin/loop` для CLI

---

## Перенос продукта в другой репозиторий / машину

1. Скопируйте в корень продукта:
   - `Makefile` (из `make/Makefile.product.example`)
   - при необходимости `.dev-hub` с путём к хабу
2. На новой машине клонируйте dev-hub и продукт
3. Выполните `make hub-link` из продукта
4. Reload Window в Cursor

Общие Make-цели живут в `dev-hub/make/product.mk` — **не копируйте** этот файл в продукт.

---

## Отключение (hub-unlink)

Удаляет symlinks, оставляет `AGENTS.md` и `.dev-hub`:

```bash
make hub-unlink
# или
~/PyProject/dev-hub/bin/hub-unlink ~/PyProject/my-product
```

---

## Разработка самого dev-hub

Когда вы правите хаб (эпики `T-HUB-*`):

- Открывайте папку **`dev-hub`** в Cursor
- `PROJECT_ROOT=dev-hub` при loop: `./bin/loop . gpt`
- Артефакты — в `dev-hub/memory-bank/`

Не смешивайте hub-эпики с product `memory-bank/`.

---

## Частые ошибки

| Ошибка | Почему плохо | Что делать |
|--------|-------------|------------|
| Multi-root workspace product+hub | Два `memory-bank/`, агент пишет не туда | Открыть **только** продукт |
| Product-эпики в `dev-hub/memory-bank/` | Anti-mix нарушен | Эпики продукта — только в `$PROJECT_ROOT/memory-bank/` |
| Нет `make hub-link` после клона | Rules/skills не видны в Cursor | `make hub-link` + Reload Window |
| `DEV_HUB not found` в Make | Нет `.dev-hub`, нет `../dev-hub` | Создать `.dev-hub` или положить хаб рядом |
| Ручной symlink `.claude` → hub | Конфликт с hub-link / runtime | Использовать `bin/hub-link` |

---

## DSH Runtime (opt-in, preview)

По умолчанию loop использует Claude Code runtime. Для DSH:

```bash
EPIC_RUNTIME=dsh ~/PyProject/dev-hub/bin/loop ~/PyProject/my-product gpt
```

Подробности: [`docs/runbooks/dsh-loop-pilot.md`](docs/runbooks/dsh-loop-pilot.md), [`dsh/README.md`](dsh/README.md).

---

## Dashboard (метрики harness)

```bash
python3 -m loop.context_loop dashboard-render [--days 7] [--format html|json|both]
```

Отчёты: `runtime/<project>/reports/`.

Переменная `EPIC_DASHBOARD_HALT_WARN_RATE` (default `0.50`) — порог halt rate для `loop doctor`.

---

## Layout dev-hub (справочно)

```
dev-hub/
  .cursor/rules · templates    # workflow rules (BACK PLAN, …)
  .claude/                     # hooks, agents, skills, project.env
  .agents/skills/              # общие skills
  loop/                        # автоцикл, context_loop.py
  runtime/<project>/           # loop state per product
  projects/<slug>/             # optional env overrides (см. projects/README.md)
  bin/loop · bin/hub-link      # CLI entrypoints
  make/product.mk              # shared Make targets для продуктов
  workspaces/                  # заготовки; multi-root не рекомендуем
```

---

## Команды ролей

`BACK PLAN`, `BACK IMPLEMENT`, `FRONT QA`, `INTEG GAP`, … распознаются через rules/skills хаба (после `hub-link` или plugin). В git продукта эти файлы **не** хранятся — только symlinks.

Документация по loop: [`loop/README.md`](loop/README.md), [`loop/WORKFLOW.md`](loop/WORKFLOW.md).
