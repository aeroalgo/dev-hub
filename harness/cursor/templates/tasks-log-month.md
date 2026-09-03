# Delivery log — шаблон месяца

Скопировать в `memory-bank/tasks/log/YYYY-MM.md` при первом FINISH месяца.

```markdown
# Delivery log — YYYY-MM

Сквозная хронология эпиков. **Пишет `finalize-step` на IMPLEMENT sNN.** Не в `load_now`. Руками — PLAN/DECOMPOSE/QA/REFLECT/ARCHIVE.

## Timeline

| Дата | Task | Событие | Артефакт |
|------|------|---------|----------|
| YYYY-MM-DD | T-xxx | BACK IMPLEMENT sNN | [sNN-slug.md](back/implement/.../sNN-slug.md) |
```

На смене фазы эпика `finalize-step` обновляет §Последние события в `tasks.md` (хвост, max 5). Агент не дублирует last-5 на каждый sNN.
