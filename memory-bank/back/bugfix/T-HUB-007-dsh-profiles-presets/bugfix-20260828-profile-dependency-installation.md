# BACK BUGFIX — T-HUB-007-dsh-profiles-presets — profile dependency installation

- **Дата:** 2026-08-28
- **Источник:** `memory-bank/back/qa/T-HUB-007-dsh-profiles-presets/qa-20260828-dsh-profiles-presets.yaml`, Fix plan B1/B2
- **Эпик:** `T-HUB-007-dsh-profiles-presets`
- **Статус:** исправление подтверждено targeted regression и DSH smoke; требуется повторный BACK QA

## Симптом

После `dsh/scripts/install-profiles.sh` профиль копировался в `$DSH_HOME/profiles/`, но `dsh --profile epic-implement --dump-config` завершался ошибкой `cannot resolve profile bundle "dsh-phase-models"`. Причина проявлялась в чистом временном `DSH_HOME`, поэтому предыдущий профильный smoke не подтверждал установочный путь.

## Root cause

Установщик копировал только каталоги профилей. В каждом `package.json` локальная зависимость `dsh-phase-models` задана как `file:../../patches`; после копирования в `$DSH_HOME/profiles/epic-*` путь ожидает `$DSH_HOME/patches`, которого установщик не создавал. Кроме того, зависимости профилей не устанавливались, поэтому DSH не мог разрешить bundle по `node_modules`.

## Исправление

- `dsh/scripts/install-profiles.sh` теперь проверяет наличие `pnpm`.
- Установщик копирует `dsh/patches` в `$DSH_HOME/patches` до установки профилей.
- После копирования каждого профиля выполняется `pnpm install --ignore-scripts`, включая локальный `dsh-phase-models`.
- `--dry-run` остаётся без изменений файловой системы; `--link` продолжает поддерживаться и устанавливает зависимости в linked profile.
- `dsh/README.md` документирует prerequisite `pnpm`, локальный bundle, manual recovery для manually copied profiles и проверку всех восьми `dump-config` smoke.
- Добавлен regression test, который устанавливает профили во временный `DSH_HOME` и проверяет наличие `node_modules/dsh-phase-models/package.json` для всех фаз.

## Проверка

- `bash -n dsh/scripts/install-profiles.sh` — PASS.
- `timeout 300s .venv/bin/pytest loop/tests/test_dsh_profile_mapping.py -q --tb=line` — `26 passed`.
- `DSH_HOME=<tmp> timeout 300s bash dsh/scripts/install-profiles.sh` — PASS; все восемь локальных bundle установлены.
- `DSH_HOME=<tmp> timeout 300s dsh --profile epic-<phase> --dump-config` для `implement`, `qa`, `decompose`, `plan`, `creative`, `audit`, `bugfix`, `reflect` — PASS.
- `--dry-run` не создаёт `$DSH_HOME/profiles`; `--link` создаёт symlink и проходит dependency installation — PASS.
- Свежая проверка в чистом временном `DSH_HOME`: installer завершился с `rc=0`; ровно 8 профилей установлены, для всех 8 найден `node_modules/dsh-phase-models/package.json`; `dsh --profile epic-<phase> --dump-config` для всех 8 фаз завершился с `rc=0` и содержит `dsh-phase-models`.
- Pre-FINISH verify: `VERDICT: PASS`; targeted regression повторно подтверждён — `26 passed`.

## Acceptance

- [x] B1: installer provisions `dsh-phase-models` and copied profiles boot.
- [x] B2: README documents executable installation and smoke prerequisites.
- [x] All eight phase profiles pass `--dump-config` after clean installation.
- [x] No package lifecycle scripts are executed by installer dependency provisioning.
- [x] Existing profile mapping regression remains green.

## Следующий шаг

`BACK QA T-HUB-007-dsh-profiles-presets` — повторить эпический QA с тем же scope s01–s07, свежим full-suite evidence и всеми восемью DSH smoke. До QA pass переход к REFLECT запрещён.
