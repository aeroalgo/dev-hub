## Epic

### Outcome

Lifecycle arm, handoff, evidence and BUGFIX finish use one canonical typed transition path. Старые arm bodies, raw handoff salvage, manual evidence и artifact-only finish больше не могут обходить новые границы.

### In
- migration всех direct callers к canonical transition owner;
- typed handoff/evidence enforcement;
- удаление legacy lifecycle branches и тестов старого контракта.

### Out
Новые lifecycle features, историческое чтение dead REFLECT events и operational session recovery.

### Done when
1. Valid phase/QA/BUGFIX flow сохраняет прежний результат.
2. Старый arm/handoff/evidence/finish обход завершается ошибкой.
3. Тесты доказывают behavior и fail-closed enforcement.

### Forbidden after

два transition owner · raw dict salvage · manual PASS · artifact-only finish · старый API «на совместимость»

### Chat decisions

- Existing `arm_phase` и typed receipt являются replacement owner; новый parallel abstraction не создаётся.

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
