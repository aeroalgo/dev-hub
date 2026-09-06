## Epic

### Outcome
Инвентарь устаревшего — документ, не рассказ. Parent не проектирует по прозе «нашёл вот это». Агент только фиксирует поверхности под замену, без дизайна нового. Нет типа документа — нет inventory.

### In
- отдельный READ-ONLY kind, не расширение explorer
- каждый item с явной меткой замены, не «info/consider»
- scope задаёт decompose, не «на глаз»
- тот же класс machine-документа, что остальной session contract

### Out
регистрация+stop pipeline · session start/finish · ownership v2

### Done when
1. parent не может принять прозу как inventory SoT
2. explorer не выполняет эту роль
3. нет типа / нет mark → запись невалидна

### Forbidden after
HOW/dual-path в ответе агента · нейтральный mark · inventory = grep parent’а для дизайна

### Chat decisions
- as-built читается как sunset (что удалить), не шаблон нового
- zero design в ответе агента

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
