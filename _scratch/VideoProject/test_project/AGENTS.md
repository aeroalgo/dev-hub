# test_project — video production agent

Ты управляешь полным циклом ролика в этой папке. Не монтируй «на глаз» — только через артефакты и фазы.

## Корень правды

- Бриф: `briefs/*.md`
- Состояние проекта: `work/project.yaml` (единственный source of truth по shot’ам)
- Выход: `out/`
- Логи прогонов: `logs/`

## Фазы (строго по порядку)

1. `plan` — script + shot list → обновить `work/project.yaml`
2. `keyframes` — картинки раскадровки → `work/shots/Sxx_key.png`, status `image_ok`
3. `generate` — image→video / text→video → `work/shots/Sxx.mp4`, status `video_ok`
4. `audio` — VO / music → `work/audio/`
5. `assemble` — склейка → `work/assembly/master.mp4` → `out/final.mp4`
6. `qc` — contact sheet + чеклист → `work/qc/` → fix по `shot_id` или `done`

Не начинай следующую фазу, пока предыдущая не закрыта для нужных shot’ов (см. `phase` в `project.yaml`).

## Правила

- Итерации только по `shot_id` (например redo `S03`), не перегенерируй весь ролик.
- Пока `image_ok` нет — видео для shot не генерировать.
- Пиши промпты и пути рядом со статусом в `project.yaml`.
- Бюджет: не превышать `budget` в `project.yaml` (max_shots / max_redo / notes).
- Human gate: после `keyframes` и перед дорогим `generate` — кратко спроси OK, если в brief не стоит `auto: true`.

## Команды пользователя (ожидай такие)

- «фаза plan» / «фаза keyframes» / «фаза generate» / «assemble» / «qc»
- «redo S02»
- «смени стиль на … и обнови pending shots»

## MCP

Используй подключённые MCP-тулы (filesystem / kinocut / gen). Если тула нет — обнови yaml и остановись с явным `BLOCKED: missing tool …`, не имитируй файлы.
