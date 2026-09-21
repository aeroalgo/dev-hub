# Запуск loop

Loop запускается только Python-скриптом `bin/loop.py`. `make` используется
только для подключения проекта (`make hub-link` / `make hub-unlink`).

Из корня продукта:

```bash
EPIC_RUNTIME=codex python3 "$DEV_HUB/bin/loop.py" \
  "$PWD" T-054-skyro-quality-dashboard-ui cx/gpt-5.6-luna-max \
  --role front
```

Эквивалентно в явном формате:

```bash
python3 "$DEV_HUB/bin/loop.py" run \
  --project "$PWD" \
  --epic T-054-skyro-quality-dashboard-ui \
  --role front \
  --runtime codex \
  --model cx/gpt-5.6-luna-max
```

Служебные команды:

```bash
python3 "$DEV_HUB/bin/loop.py" status --project "$PWD" --json
python3 "$DEV_HUB/bin/loop.py" doctor --project "$PWD" --json
python3 "$DEV_HUB/bin/loop.py" halt --project "$PWD" --reason "manual stop"
```

## Настройки и выбор модели

Loop читает корневой `.env` через `pydantic-settings`. `.claude/` содержит
только Claude Code integration и не является источником настроек цикла.

При каждом запуске сессии модель выбирается заново в таком порядке:

1. явный `--model` или legacy-позиционная модель;
2. `LOOP_STEP_MODELS` — JSON-карта (`{"S01":"...","QA":"..."}`);
3. phase-модель (`LOOP_MODEL_IMPLEMENT`, `LOOP_MODEL_QA`, …);
4. `LOOP_MODEL`.

Старые имена `PROJECT_LOOP_<PHASE>_MODEL` поддерживаются как совместимый
alias. Если модель не найдена, loop останавливается с `model_required`; тихого
fallback на случайную/default-модель нет.

Workflow hooks получают `LOOP_ACTIVE=1` только от `bin/loop.py` и поэтому
работают внутри loop-сессии. В обычном Claude/Codex чате hook-dispatch делает
no-op.

Модель передаётся без локального whitelist. Ограничение доступности модели
проверяет сам выбранный runtime и его аккаунт; ошибка runtime выводится вместе
с `epic`, `role`, `phase`, `step`, `attempt`, `cursor_path` и `session_log`.
