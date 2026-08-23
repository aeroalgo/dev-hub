# Containers — dev-hub

**Last refresh:** 2026-08-16 · BACK VAN  
**Status:** `n/a`

## Обоснование

В корне `dev-hub` **нет** `docker-compose*.yml`, `Dockerfile*`, k8s manifests. Runtime — host processes (bash/python + Claude CLI + Cursor).

## Что есть вместо compose

| Артефакт | Роль |
|----------|------|
| `bin/loop` + `loop/loop.sh` | process orchestration |
| `runtime/<slug>/` | local state volumes (filesystem) |
| `.claude/project.env` | env «compose» для loop |

## Networks / ports

- Публикуемых container ports нет.
- Опционально loop ходит на `PROJECT_OUTPUT_SUMMARY_URL` (внешний summary endpoint из project.env) — не сервис хаба.

## Follow-up

Если понадобится containerize loop — отдельный PLAN; сейчас as-built = host tooling.
