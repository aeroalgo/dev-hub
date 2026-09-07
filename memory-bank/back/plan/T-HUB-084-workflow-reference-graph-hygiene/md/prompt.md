## Epic

### Outcome

Каждая обязательная workflow dependency выражена один раз с понятным владельцем и моментом загрузки.

### In

- Direct/transitive shared edges.
- Проверяемый ownership graph.
- Безопасное удаление proven-dead source.

### Out

Инлайнинг больших policies, архивы и blind deletion.

### Done when

1. Duplicate, dangling или ambiguous edge ломает validation.
2. Единственный owner не может быть удалён незаметно.

### Forbidden after

Repeated mandatory Read · implicit owner · compatibility alias to dead source.

### Chat decisions

- n/a — no pre-plan chat

---

## Covering

### Outcome

Цепочки чтения меньше и однозначнее при сохранении fail-closed workflow discipline.

### Axes

- Каноническая навигация режима.
- Общие gate contracts без копий.
- Ролевые политики без лишнего общего текста.
- Граф ссылок без повторных и мёртвых рёбер.

### Invariants

- Сокращение Read не отменяет обязательный guard.
- Один механизм имеет один source of truth.

### Out

Изменение продуктовых outcomes или verification policy.

### Done when

1. Лишний Read не нужен для прежней семантики.
2. Устаревшая инструкция автоматически обнаруживается.

### Forbidden after

Mega-plan · optional route · duplicate active source · использование этого текста как HOW.

### Chat decisions

- n/a — no pre-plan chat
