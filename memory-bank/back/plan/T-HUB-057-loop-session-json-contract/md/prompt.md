## Epic

### Outcome
Сессия — конвейер typed-записей: старт, emit, проверка, retry формы, смысл, ремонт, финиш, следующий шаг ≠ только что закрытый. Валидатор — код, не «агент уверен». Обход конвейера вручную не считается сессией.

### In
- один machine path сессии
- ошибка формы ≠ смысловой FAIL — разные ответы, нельзя смешивать
- schema-invalid → тот же агент переиздаёт, ограниченно
- post-finish cursor не возвращает на только что закрытый шаг

### Out
новый inventory-агент · ownership mismatch код · doctor CLI drift

### Done when
1. проза / ручной Write не проводят start/finish как SoT
2. форму нельзя лечить ремонтом смысла и наоборот
3. re-arm того же шага после finish нельзя без ошибки

### Forbidden after
«я проверил в голове» · regex salvage · silent accept · dual prose path как primary

### Chat decisions
- runtime validate-before-emit, не LLM self-check
- schema-retry vs semantic FAIL vs next≠current — три разных правила

---

## Covering

### Outcome
Сессия и её агенты говорят с машиной только документами. Parent не проектирует по прозе. Конвейер один: нет типа / нет тела — нет шага вперёд.

### Axes
- session path: typed start→emit→validate→retry/repair→finish→next≠current
- inventory устаревшего = typed документ с mark REPLACE, не рассказ

### Invariants
- fenced JSON + registry schema_id → pydantic
- агент вызывает validate, не заменяет его
- READ-ONLY inventory не содержит дизайна нового пути

### Out
leftover CLI/doctor drift · stop ownership · sunset в registry

### Done when
1. обе оси нельзя обойти прозой
2. session-эпик не пишет sunset-агента; inventory-эпик не переписывает session finish

### Forbidden after
склеить session+inventory · explorer «ещё и sunset» · этот Covering как SoT REPLAN · читать соседние plan

### Chat decisions
- сначала канон session JSON, потом новый kind документа
- parent строит новый SoT поверх inventory, не расширяя старый путь
