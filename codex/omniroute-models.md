# Codex: OmniRoute и мультимодели (Gemini и др.)

Мультимодельность в Codex идёт через **OmniRoute**, а не через нативный ChatGPT login.

## Активный конфиг: `~/.codex/config.toml`

Ключевые поля:

```toml
model = "gpt-5.6-luna"
model_reasoning_effort = "high"
model_catalog_json = "/home/aero/.codex/model-catalog.json"
model_provider = "omniroute"

[model_providers.omniroute]
name = "OmniRoute"
base_url = "http://localhost:20128/v1"
env_key = "OMNIROUTE_API_KEY"
wire_api = "responses"
```

| Поле | Смысл |
|------|--------|
| `model_provider = "omniroute"` | трафик идёт в локальный прокси `http://localhost:20128/v1` |
| `model_catalog_json` | кастомный picker (Gemini / Claude / Grok рядом с GPT) |
| ключ | `OMNIROUTE_API_KEY` или файл `~/.codex/.omniroute_key` |

Шаблон для setup: [`omniroute.config.toml`](omniroute.config.toml). Установка:

```bash
./codex/bin/setup-omniroute.sh
```

В `dev-hub/.codex/config.toml` только отключение skills-каталога — провайдеры моделей там не задаются.

## Откуда берутся Gemini и остальные

Источник списка: `~/.claude/extra-models.json` → мержится в каталог:

```bash
./codex/bin/patch-model-catalog.py apply
./codex/bin/patch-model-catalog.py status
```

Результат: `~/.codex/model-catalog.json` + проводка `model_catalog_json` в `config.toml`.

Перезапускайте `apply` после правок `extra-models.json` или апгрейда `@openai/codex`.

### Модели в каталоге (текущий снимок)

| Slug | Назначение |
|------|------------|
| `antigravity/gemini-3.7-flash-high` | Gemini, daily / cheap-strong |
| `antigravity/gemini-3.7-flash-medium` | Gemini, daily / cheap-strong |
| `antigravity/gemini-3.7-flash-low` | Gemini, subagents / explore |
| `antigravity/claude-sonnet-4-6` | Claude через Antigravity |
| `antigravity/claude-sonnet-5` | Claude через Antigravity |
| `agy/claude-sonnet-5` | Claude (agy) |
| `cc/claude-sonnet-5` | Claude (cc) |
| `cx/gpt-5.6-luna` | GPT через OmniRoute |
| `gc/grok-4.6` | Grok |
| стоковые `gpt-5.6-*` и др. | нативные GPT |

## Как запускать

```bash
./codex/bin/codex-omniroute.sh
# или с явной моделью:
codex -c 'model="antigravity/gemini-3.7-flash-high"' …
```

Wrapper форсирует `model_provider=omniroute`. `which-codex.sh` сам выбирает wrapper, если в `config.toml` есть OmniRoute и есть key-файл.

Отключить wrapper-routing:

```bash
CODEX_USE_OMNIROUTE=0 codex …
```

## Без OmniRoute (прямой ChatGPT login)

```bash
codex login
```

Работают только нативные GPT-slug’и (`gpt-5.6-luna` + `model_reasoning_effort=…`). Префиксы вроде `cx/` / `antigravity/` на прямом ChatGPT auth **не** проходят.

## Связанные файлы

| Путь | Роль |
|------|------|
| `~/.codex/config.toml` | активный user-level конфиг |
| `codex/omniroute.config.toml` | шаблон провайдера |
| `codex/bin/setup-omniroute.sh` | установка |
| `codex/bin/codex-omniroute.sh` | wrapper запуска |
| `codex/bin/patch-model-catalog.py` | merge каталога моделей |
| `~/.claude/extra-models.json` | источник Gemini/Claude/Grok slug’ов |
| `~/.codex/model-catalog.json` | итоговый picker для CLI/extension |
| [`README.md`](README.md) | полный контракт интеграции Codex |
