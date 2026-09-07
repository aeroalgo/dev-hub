# Как запускать loop с разными runtime

Этот файл содержит однострочные команды для запуска loop из корня репозитория. Формат команды: `runtime + epic + model`. Команда использует текущий каталог как `PROJECT_ROOT`.

## Codex через OmniRoute

Команда запускает указанный эпик и передаёт OmniRoute ID как позиционную модель:

```bash
./bin/loop codex decompose-T-HUB-XXX 'cx/gpt-5.6-luna-xhigh'
```

Другой пример с моделью Claude, опубликованной OmniRoute:

```bash
./bin/loop codex decompose-T-HUB-XXX 'agy/claude-sonnet-4-6'
```

Codex runtime использует OmniRoute, если в `~/.codex/config.toml` настроен провайдер `omniroute` и существует `~/.codex/.omniroute_key`.

## Claude Code

Эта команда использует Claude Code runtime и передаёт выбранную модель:

```bash
./bin/loop claude decompose-T-HUB-XXX 'antigravity/claude-sonnet-4-6'
```

## DSH

DSH runtime берёт модель из phase-профиля и переменных `PROJECT_LOOP_<PHASE>_MODEL`:

```bash
./bin/loop dsh decompose-T-HUB-XXX 'gpt'
```

Перед первым запуском установите профили DSH:

```bash
./dsh/scripts/install-profiles.sh
```

## Служебные команды

Показать состояние loop:

```bash
./bin/loop . --status
```

Показать справку:

```bash
./bin/loop . --help
```

Запустить loop для другого репозитория можно из его корня, вызвав абсолютный путь к `bin/loop`:

```bash
~/PyProject/dev-hub/bin/loop codex decompose-T-HUB-XXX \
  'cx/gpt-5.6-luna-xhigh'
```

## Приоритет модели

Переменная `PROJECT_LOOP_<PHASE>_MODEL` из `.claude/project.env` имеет приоритет над позиционной моделью. Сейчас `PROJECT_LOOP_DECOMPOSE_MODEL` задана как `cx/gpt-5.6-luna-max`, поэтому DECOMPOSE использует её. Для остальных фаз без отдельного override применяется модель из команды.

Если OmniRoute ограничивает выбранную модель или заменяет её, loop останавливается с `model_substitution`, а не продолжает работу на другой модели.

Подробности: [`docs/runbooks/codex-loop-pilot.md`](docs/runbooks/codex-loop-pilot.md), [`docs/runbooks/dsh-loop-pilot.md`](docs/runbooks/dsh-loop-pilot.md) и [`loop/README.md`](loop/README.md).
