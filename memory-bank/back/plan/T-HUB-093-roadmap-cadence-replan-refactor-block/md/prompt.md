## Epic

### Outcome
Когда cadence уже в фазе дожима, loop дожимает critical outcome-дыры последних двух feature на тех же id через REPLAN, и только после закрытия/skip этой фазы вставляет и армает PLAN REFACTOR (или фиксирует noop) — порядок не переставить.

### In
- Переходы phase replan → refactor на существующем cadence SoT
- Critical-only gap evidence / skip с provenance; one-hop
- Upsert/arm отдельного refactor epic или noop evidence
- Enforce: refactor нельзя до конца replan phase

### Out
- Создание cadence SoT / счётчика every-2 (другая ось)
- reconcile from-queue / resync HOW / Kind I docs хвоста
- Sliding window; REPLAN-steps в чужой feature; косметика в queue

### Done when
1. Пока replan phase не closed/skipped по обоим id пары — arm PLAN REFACTOR fail-closed.
2. После закрытия replan — либо refactor epic `kind: refactor` в работе/голове, либо noop evidence, затем phase готова к хвосту.
3. Critical gaps гонят same-id REPLAN; пустой critical → skip с evidence, не silent forever без записи.

### Forbidden after
refactor-before-replan · replan→replan · dual-path «сразу feature» из этой оси · carry FR в steps соседа

### Chat decisions
- В блоке всегда сначала REPLAN, потом PLAN REFACTOR
- Дожимаем пару; Refactor = новый epic
- Critical-only; noop допустим с evidence

---

## Covering

### Outcome
Каждые два закрытых feature запускают упорядоченный cadence: дожим пары, затем наведение порядка отдельным refactor-epic, затем сверка хвоста очереди; без скользящего окна и без голодания новых фич вне блока.

### Axes
- Foundation: typed SoT, счётчик, пауза feature-advance
- Block: REPLAN пары critical-only, затем PLAN REFACTOR epic/noop
- Tail: reconcile queue + resync HOW, resume

### Invariants
- В блоке всегда REPLAN раньше Refactor
- Дожим — те же id пары, не steps чужого feature
- prompt §Epic иммутабелен при resync
- replan→replan и sliding window запрещены
- Refactor/cadence meta не крутят счётчик every-2

### Out
- Обязательный тройной проход каждого эпика
- Carry FR прошлого в decompose соседа
- Cadence для других ролей в этой нарезке

### Done when
1. Нельзя silent проехать третий feature после пары без cadence phase.
2. Нельзя армить Refactor до закрытия REPLAN phase.
3. Нельзя resume feature при необработанном HIGH drift хвоста после блока.

### Forbidden after
склеить оси в mega-plan · Covering как SoT REPLAN · читать соседние plan/

### Chat decisions
- every-2; REPLAN затем Refactor; scope = пара; после блока — хвост; без окна
