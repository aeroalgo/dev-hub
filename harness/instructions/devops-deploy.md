# DEVOPS DEPLOY — инструкция агенту

Для выкладки и проверки проекта используй только общий runner хаба:

```bash
"$DEV_HUB/bin/devops-deploy" --project "$PWD" check
"$DEV_HUB/bin/devops-deploy" --project "$PWD" apply
```

Правила:

1. Сначала `check`; если он завершился неуспешно, `apply` не запускать.
2. Для JSON используй `--json`; не смешивай JSON с диагностикой в stdout.
3. Не запускай напрямую проектный adapter, `ssh`, `docker`, `docker compose`,
   `systemctl`, `apt`, `rsync` или команды удаления для обхода runner.
4. Не меняй `projects/<project-id>/deploy.json` ради обхода проверки.
5. `apply` должен пройти preflight и postflight. PASS означает, что declared
   SSH targets, units, контейнеры, listeners, TCP/HTTP endpoints и проектный
   smoke успешно проверены.
6. При FAIL покажи путь к JSON-отчёту и остановись. Не объявляй частичный
   перенос успешным и не удаляй старый контур.

Манифест проекта лежит в `dev-hub/projects/<project-basename>/deploy.json`.
Он содержит только allowlist целей и проверок; секреты и произвольные shell
команды туда не записываются.
