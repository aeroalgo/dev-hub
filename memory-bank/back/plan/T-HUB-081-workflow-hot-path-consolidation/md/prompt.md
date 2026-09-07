## Epic

### Outcome

Краткий маршрут и полный workflow живут в одном каноническом документе; обязательные гейты не теряются при сокращении чтения.

### In

- Навигация hot path.
- Удаление duplicate active instruction sources.

### Out

Изменение runtime, scope lock или длинных lean contracts.

### Done when

1. У режима один источник навигации.
2. Старая ссылка или пропущенный guard диагностируются.

### Forbidden after

Два quick path · ссылка на removed source · ослабленный gate.

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
