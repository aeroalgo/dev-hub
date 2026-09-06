## Epic

### Outcome
Вердикт субагента — не строка в прозе. SoT — канонический документ известного типа. Нет документа → нет решения. Парсер не «спасает» смысл из текста.

### In
- managed verify/review завершает сессию документом
- runtime validate того же типа, что заявлен
- пока проза и документ оба принимаются — граница не закрыта: искать все входы

### Out
typed LLM-summary · sidecar write · ownership/полёт · schema-retry taxonomy

### Done when
1. PASS/FAIL нельзя провести без канонического тела
2. prose-путь нельзя использовать без ошибки
3. второй вход (regex / payload без тела) закрыт

### Forbidden after
VERDICT-строка как SoT · salvage при падении validate · «в голове ок»

### Chat decisions
- REDO v4: JSON-in-prompt, без regex как канона
- Primary path = fence → model_validate → persist

---

## Covering

### Outcome
На любой границе LLM/агент → машина SoT = канонический документ известного типа. Проза и regex-salvage не проводят решение.

### Axes
- типизированный выход модели, не free-text
- запись на диск только после validate
- вердикт субагента = документ, не строка в прозе

### Invariants
- pydantic валидирует структуру; структура на границе = JSON (или YAML frontmatter файла)
- нет документа → нет решения
- слой описания («агент уверен») не заменяет runtime validate

### Out
session start/finish конвейер · sunset inventory agent · ownership/полёт

### Done when
1. ни одна ось не принимает прозу как machine SoT
2. эпик не закрывает соседнюю ось «заодно»

### Forbidden after
склеить typed-output и gate-verdict в один «просто pydantic» · regex как канон · этот Covering как SoT REPLAN · читать соседние plan

### Chat decisions
- Axiom: structured data on LLM→machine boundary = JSON; prose VERDICT не machine input
