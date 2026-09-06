## Epic

### Outcome
Машина не читает свободный текст модели как факт. На границе «модель → код» только типизированный объект. Если структура не сошлась — ошибка формы, не «почти ок». Человеческий рендер вторичен.

### In
- типизированный выход LLM на этой границе
- отказ формы, если объект не сошёлся
- dual-path сырого текста не считать успехом, пока он жив

### Out
verdict субагента / fence на stop · sidecar validate-on-write · session pipeline

### Done when
1. код потребляет только типизированный объект, не сырой ответ
2. старый free-text путь нельзя использовать как SoT без ошибки (или он удалён)

### Forbidden after
regex по прозе модели как machine input · silent accept частичного объекта · «рендер для человека = валидация»

### Chat decisions
- Structured client вместо сырого HTTP; fallback free-text — временный, не SoT
- n/a — решения зафиксированы в plan axiom, отдельного pre-plan чата в артефакте нет

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
