## Epic

### Outcome
После завершения REPLAN→Refactor блока loop сверяет хвост roadmap queue с деревом репо, при HIGH drift требует resync/invalidate HOW (без правки §Epic prompt) и только тогда сбрасывает cadence в idle и снова армает feature.

### In
- reconcile mode from-queue по ids в `queue:`
- resume gate: HIGH без resync-record → запрет feature advance
- политика resync/invalidate stale plan HOW; prompt §Epic иммутабелен
- reset counter/phase после успешного хвоста
- Kind I: инструкции cadence without sliding window

### Out
- Foundation counter/SoT (уже ship)
- Логика REPLAN arm и вставки Refactor epic (уже ship)
- Semantic LLM-перепись всех prompt; FRONT/INTEG

### Done when
1. `reconcile --from-queue` (или API) отдаёт reports по текущему хвосту queue.
2. При HIGH без зафиксированного resync — resume feature fail-closed.
3. После ok/resync — phase idle, feature advance снова работает; rules не учат sliding window как канон.

### Forbidden after
resume при сыром HIGH · менять §Epic prompt в resync · soft-ignore drift · вернуть window-канон в instructions

### Chat decisions
- После блока — reconcile/resync хвоста
- §Epic иммутабелен; HOW можно освежить / JIT у головы
- Нет sliding window в каноне

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
