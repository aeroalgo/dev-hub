# Установка dev-hub

Краткий runbook. Полный контекст: корневой [`README.md`](../README.md).

## 1. Установить хаб (один раз на машину)

```bash
git clone <url-dev-hub> ~/PyProject/dev-hub
cd ~/PyProject/dev-hub

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# при необходимости: EPIC_RUNTIME=claude|codex, LOOP_MODEL*, board/Bitrix keys

bin/pytest -q --tb=line   # опционально: self-test хаба
```

**Нужно:** Python 3.12+, git, jq; для loop — Claude CLI и/или Codex CLI (≥ 0.152).

## 2. Подключить продукт

```bash
cd ~/PyProject/my-product

cp ~/PyProject/dev-hub/make/Makefile.product.example ./Makefile
# опционально:
cp ~/PyProject/dev-hub/harness/templates/dev-hub.project.yaml ./dev-hub.project.yaml

make hub-link
# = bin/hub-link --with-skills  (режим alongside)

mkdir -p memory-bank
cursor .
# Developer → Reload Window
```

Если хаб не сосед (`../dev-hub`):

```bash
echo '/abs/path/to/dev-hub' > .dev-hub
# или: DEV_HUB=/abs/path/to/dev-hub make hub-link
```

## 3. Режимы hub-link

| Режим | Команда | Назначение |
|-------|---------|------------|
| **alongside** (default) | `make hub-link` / `bin/hub-link --with-skills` | Продукт: symlink harness + rules/skills overlays, не ломает чужие файлы (fail-closed) |
| **full** | `bin/hub-link --mode full` | Полная реплика shell хаба (dogfood / CI fixtures) |

Снять:

```bash
make hub-unlink
# или: bin/hub-unlink [--mode alongside|full]
```

Детали: [`harness/README.md`](../harness/README.md).

## 4. Проверка

```bash
make hub-info
ls -la .dev-hub harness .cursor/rules AGENTS.md CLAUDE.md .agents/skills
python3 "$(sed -n '1p' .dev-hub)/bin/loop.py" doctor --project "$PWD" --json
```

В Cursor должны быть видны rules/skills; команда вроде `BACK VAN` распознаётся роутером.

## 5. Первый loop (после VAN/PLAN)

```bash
# из продукта
make loop ARGS="codex <epic_id> <model> [low|medium|high|xhigh]"

# или напрямую
python3 "$DEV_HUB/bin/loop.py" run \
  --project "$PWD" \
  --epic <epic_id> \
  --runtime codex \
  --model <model> \
  --role auto
```

Канон CLI: [`loop/README.md`](../loop/README.md).  
Codex: [`runbooks/codex-loop-pilot.md`](runbooks/codex-loop-pilot.md).

## 6. Обновление хаба

```bash
cd ~/PyProject/dev-hub
git pull
source .venv/bin/activate
pip install -r requirements-dev.txt

cd ~/PyProject/my-product
make hub-link          # обновить symlinks / router stub
# Reload Window в Cursor
```

`product.mk` подтягивается через `include` — копировать его в продукт не нужно.

## 7. Частые сбои

| Симптом | Действие |
|---------|----------|
| `DEV_HUB not found` | `.dev-hub` или `DEV_HUB=` или соседний `../dev-hub` |
| `exists and is not a symlink` | убрать/переименовать локальный конфликт, повторить link |
| rules не видны в Cursor | `make hub-link` + Reload Window; не multi-root с хабом |
| `model_required` у loop | задать `--model` или `LOOP_MODEL*` в `.env` хаба |
| два `memory-bank/` | открыта только папка продукта |

## 8. Board / Bitrix (после hub-link)

`make hub-link` один раз кладёт в продукт (если файлов ещё нет):

| Путь | Назначение |
|------|------------|
| `.loop/board-projection.yaml` (+ `.example`) | фазы → колонки, role allowlist |
| `.loop/board-actors.yaml` (+ `.example`) | кто постановщик/исполнитель по эпику |
| `scripts/board-sync.sh` | sync с учётом актёров |
| `memory-bank/product/board-publish.md` | правило «после PLAN → доска» |

Дальше в продукте:

```bash
cp .env.example .env   # или дописать LOOP_BOARD_* / BITRIX_* из хаба .env.example
# отредактировать .loop/board-actors.yaml (epics → sokolov|erokhin|…)
./scripts/board-sync.sh --all
```

Rules (всегда через symlink harness): `workflow-board-sync.mdc`, `workflow-board-after-plan.mdc`, `workflow-board-docs.mdc`.

## Конфиг, который можно коммитить в продукт

- `Makefile` (тонкий wrapper)
- `.dev-hub` (путь к tooling)
- `dev-hub.project.yaml` (targets / workflow_pack)
- `.loop/board-actors.yaml` (+ examples), `scripts/board-sync.sh`, `memory-bank/product/board-publish.md`

**Не коммитить:** `.env` хаба с секретами, Bitrix/Plane keys, `.deploy.env` с секретами.
