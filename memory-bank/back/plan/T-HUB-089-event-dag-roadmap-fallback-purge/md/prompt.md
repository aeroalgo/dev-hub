## Epic

### Outcome

Live event, DAG и roadmap execution использует только поздние v2 contracts. Историческая миграция отделена от runtime, а старые input formats больше не запускают выполнение через скрытый adapter.

### In
- v2-only live readers and validators;
- explicit archive/migration boundary;
- удаление legacy queue, DAG, event и Markdown mirror tests.

### Out
Изменение самих v2 schemas, retention policy сверх необходимого и новые roadmap features.

### Done when
1. Valid v2 event/DAG/queue flows remain green.
2. Старый формат не превращается в live execution.
3. Архивная совместимость, если нужна, вызывается явно.

### Forbidden after

implicit adapter · legacy queue probe · Markdown mirror SoT · inferred DAG execution · archive-as-live-fallback

### Chat decisions

- Historical compatibility is allowed only as an explicit offline boundary, never as runtime fallback.

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
