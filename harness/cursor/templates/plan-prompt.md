## Epic

Outcome, In, Out, Done when, Forbidden after, Chat decisions **этого** эпика. Абстрактнее `plan.md`. Не FR/AC ids, не имена файлов, не патчи, не ID эпиков.

### Outcome
<1–3 предложения: что должно стать правдой, без HOW.>

### In
- <класс работы 1>
- <класс работы 2>

### Out
<не этот эпик — классами работы, без ID>

### Done when
1. <наблюдаемое поведение>
2. <старый обход нельзя без ошибки>

### Forbidden after
<dual-path / salvage / default / prose-as-SoT>

### Chat decisions
- <решения сессии до PLAN> | `n/a — no pre-plan chat`

---

## Covering

**Single-epic:** `n/a — single epic`

**Multi-epic:** тот же covering во всех `prompt.md` нарезки — constitution, которая охватывает все epic-промпты. Не HOW. Не копия Epic.

### Outcome
<одна правда на всю нарезку>

### Axes
Одно предложение на ось нарезки. **Без** ID эпиков, путей `plan/`, имён файлов — иначе агент пойдёт искать чужие plan.

- <ось 1>
- <ось 2>

### Invariants
- <общее всем эпикам нарезки>

### Out
<не эта нарезка — без ID>

### Done when
1. <ложный green по всем осям нельзя>
2. <эпик не закрывает чужую ось «заодно»>

### Forbidden after
склеить оси · mega-plan · этот Covering как SoT REPLAN · читать соседние `plan/`

### Chat decisions
- <решения на всю нарезку> | `n/a — no pre-plan chat`
