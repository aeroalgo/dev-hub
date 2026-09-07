## Epic

### Outcome

Общая policy роли имеет одного владельца, а уникальные обязанности каждой роли не растворяются при extraction.

### In

- Общая session/test policy.
- Role-only lifecycle, UI и contract boundaries.

### Out

Сведение ролей к одному generic workflow.

### Done when

1. Общий текст не редактируется в трёх местах.
2. Ролевая особенность не может silently исчезнуть.

### Forbidden after

Copied core prose · generic role core · снятие parent-only или lifecycle guard.

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
