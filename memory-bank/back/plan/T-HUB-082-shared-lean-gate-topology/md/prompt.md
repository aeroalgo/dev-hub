## Epic

### Outcome

Одинаковые gate contracts имеют одного владельца, а ролевые различия остаются явными и проверяемыми.

### In

- Доказанно общие lean contracts.
- Role-specific deltas.
- Защита от возврата копий.

### Out

Унификация различающихся security, UX или artifact semantics.

### Done when

1. Общая policy читается по canonical path.
2. Локальная копия или missing delta диагностируются.

### Forbidden after

Independent copy · silent fallback · placeholder вместо role boundary.

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
