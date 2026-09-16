## Epic

### Outcome
В hub нет живого DSH runtime path: выбрать или запустить DSH нельзя без ошибки; дерево реализации и тесты контракта удалены; инструкции не учат DSH как поддерживаемый runtime.

### In
- Удаление runtime adapter / registry / CLI / env wiring для DSH
- Удаление библиотечного дерева и install/helper scripts рантайма
- Удаление или перепись тестов, закрепляющих DSH-контракт
- Перепись live instruction/operator surfaces (без трогания historical epic trees)

### Out
- Перепись/удаление historical plan/qa/audit/events эпиков про DSH
- Изменение поведения Claude Code или Codex adapters (кроме снятия DSH-веток)
- Установка/удаление глобального бинаря DSH на хосте оператора

### Done when
1. `dsh` как runtime id на CLI/env/factory даёт явную ошибку и не подменяется другим runtime
2. Реализационное дерево и adapter-модуль отсутствуют; suite не требует DSH-контракт
3. Live инструкции не описывают DSH как поддерживаемый runtime

### Forbidden after
silent fallback dsh→claude · registry key «deprecated but present» · optional allow_dsh · restore adapter ради зелёных тестов · dual teaching в AGENTS/CLAUDE

### Chat decisions
- Удалить весь код/рантайм/библиотеки/тесты/связанную live-документацию DSH
- Historical эпики memory-bank не трогать
- Maximal history scrub (ранний ответ C) отменён этим решением

---

## Covering

n/a — single epic
