## Epic

### Outcome

Canonical metadata, registry и CLI boundary становятся единственными реализациями для своих supported surfaces. Подтверждённо мёртвые aliases и old routes удалены, а operational fallback не смешан с legacy workflow compatibility.

### In
- agent metadata and registry cutover;
- board/runtime dead shim removal;
- obsolete alias tests and instruction cleanup.

### Out
Operational PATH/LLM recovery, DSH aliases с живыми supported callers и новые registry features.

### Done when
1. Covered surfaces работают через canonical owner.
2. Dead aliases/handlers имеют ноль references и удалены вместе с тестами.
3. Retained operational fallbacks явно классифицированы и продолжают проходить regression.

### Forbidden after

hardcoded legacy metadata · hidden second CLI route · blind dynamic scan · удаление operational safety fallback без замены

### Chat decisions

- External/dynamic compatibility удаляется только после executable reference proof; отсутствие локального теста недостаточно.

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
