## Epic

### Outcome
После каждых двух закрытых feature-эпиков loop больше не армает третий feature: включается typed cadence SoT со счётчиком, фазой и паузой feature-lane до явного продолжения блока.

### In
- Schema cadence validate-on-write
- kind на queue row; counter только для feature
- pair buffer из двух последних feature done
- phase machine минимум: idle → replan (вход в блок); запрет feature-advance пока блок активен
- CLI/status для наблюдения SoT

### Out
- Arm/выполнение BACK REPLAN и вставка PLAN REFACTOR epic
- reconcile from-queue и resync HOW
- Скользящее окно; косметический REPLAN; FRONT/INTEG cadence

### Done when
1. Два feature `done:` подряд → phase указывает вход в cadence; `roadmap_advance` не армает новый feature.
2. `kind: refactor` done не увеличивает feature-счётчик.
3. Битый cadence SoT → fail-closed; обойти паузу silent old-advance нельзя.

### Forbidden after
optional cadence flag default off · prose-only counter · try/except на старый advance · считать non-feature в every-2

### Chat decisions
- Каждые 2 feature done → cadence
- Сначала foundation (счётчик+pause), исполнители блока — следующие оси нарезки
- Нет sliding window

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
