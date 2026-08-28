# T-FIX-999 — fake missing coverage

Фиктивный минимальный план для dry-run ANALYZE. Fixture намеренно содержит требование без шага.

## Functional requirements

- **FR-1:** Система должна делать X.
  - Coverage note: FR-1 без `sNN` mapping (намеренная дыра fixture).

## Non-functional requirements

- **NFR-1:** Latency < 100ms.

## Acceptance criteria

- **AC+ #1:** FR-1 должен быть покрыт decompose-шагом.

## Expected ANALYZE dry-run finding

- Category: `Coverage`
- Severity: `CRITICAL`
- Message: `FR-1 без sNN/decompose mapping; требование не покрыто ни одним шагом.`
- Recommendation: исправить coverage в DECOMPOSE и повторить ANALYZE до IMPLEMENT.
