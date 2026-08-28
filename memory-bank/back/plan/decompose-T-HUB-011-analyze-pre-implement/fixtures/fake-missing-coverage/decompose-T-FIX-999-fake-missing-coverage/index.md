# Decompose index — T-FIX-999

Минимальный фиктивный decompose index для dry-run ANALYZE.

- **FR-1:** отсутствует mapping на `sNN`; это намеренная missing coverage.
- `s01-stub.yaml` существует, но его `goal` и `plan_refs` не покрывают FR-1.
- Ожидаемая находка: `Category=Coverage`, `severity=CRITICAL`, сообщение указывает на FR-1 без шага.

Fixture не является рабочим эпиком и не предназначен для IMPLEMENT.
