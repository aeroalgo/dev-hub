## Epic

### Outcome

Все живые epic-артефакты и runtime lookup используют один canonical layout v2. Старые filesystem addresses и Markdown как machine source больше нельзя использовать без явной ошибки.

### In
- миграция оставшихся живых legacy artifact trees;
- rewiring path, board, reconcile и load consumers;
- удаление старых path/parser веток и связанных тестов.

### Out
Исторический archive cleanup, новый layout design и operational fallback, не связанный с epic artifact resolution.

### Done when
1. v2 plan/decompose/implement проходят через runtime entrypoints.
2. Старый layout не исполняется и не используется как fallback.
3. Тесты проверяют v2 behavior и denial старых адресов.

### Forbidden after

dual layout · Markdown machine SoT · implicit migration · silent fallback на старый путь · legacy-only green tests

### Chat decisions

- Удаление выполняется после parity migration, чтобы не потерять текущие implement artifacts.

## Covering

### Outcome

Кодовая база имеет один поздний canonical путь исполнения, а старые реализации, fallback-ветки и тесты старого контракта удалены после доказуемой миграции.

### Axes

- filesystem/layout cutover;
- lifecycle and structured state cutover;
- event, DAG and roadmap adapter cutover;
- boundary and compatibility shim cleanup.

### Invariants

- новый путь — единственный runtime SoT;
- старый путь → explicit deny/error;
- production и соответствующие obsolete tests удаляются вместе;
- архивная история не является live fallback.

### Out

Новые пользовательские возможности, изменение бизнес-поведения и operational reliability fallbacks.

### Done when

1. Все активные dual paths подтверждены пустым executable inventory.
2. Каждый удалённый тест заменён behavior/deny coverage или явно исключён как obsolete.
3. Ни один эпик не оставляет свою старую ветку «на совместимость».

### Forbidden after

mega-plan · optional SoT · hidden fallback · тесты, требующие удалённый контракт · чтение соседних plan

### Chat decisions

- Нарезка разделяет независимые runtime trees и сохраняет production consumer рядом с producer.
