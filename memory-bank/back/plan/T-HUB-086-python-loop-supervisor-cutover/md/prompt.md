## Epic

### Outcome

Автономный loop работает через один тестируемый Python supervisor с сохранением текущего операторского CLI и поведения runtime. Shell-обвязка остаётся только совместимым делегирующим entrypoint, а state, retry, timeout, halt/complete и provider contracts не получают второй реализации.

### In

- перенос process orchestration в typed Python boundary;
- сохранение публичного запуска, runtime adapters, bounded sessions и durable evidence;
- миграция тестов и активных инструкций на единственный execution path;
- fail-closed enforcement против старого shell supervisor и silent fallback.

### Out

Изменение provider capabilities, форматов memory-bank/checkpoint, бизнес-логики продуктов, параллельного DAG execution, внешних сервисов и исторических архивных документов.

### Done when

1. Операторский запуск, обычная сессия, retry, interrupt, permanent failure и terminal decision проходят через один Python path с наблюдаемыми результатами.
2. Старый shell supervisor нельзя вызвать как отдельную реализацию: он только делегирует, source-based API отсутствует, а активные инструкции не требуют его внутренних функций.

### Forbidden after

Второй supervisor рядом с Python, fallback Python → shell, silent runtime substitution, изменение state semantics ради удобства миграции и green suite, достигнутый сохранением obsolete shell tests.

### Chat decisions

- Python supervisor выбран как более удобный для поддержки и тестирования.
- Публичные команды сохраняются; совместимость достигается делегацией, а не сохранением shell orchestration.
- Scope — один vertical-slice cutover без новой runtime-функциональности.

## Covering

`n/a — single epic`
