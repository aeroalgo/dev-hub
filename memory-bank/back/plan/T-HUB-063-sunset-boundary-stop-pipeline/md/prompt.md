## Epic

### Outcome
Заявленный тип без регистрации — не тип. Managed-агент либо проходит тот же конвейер, что остальные (известен → разобран → проверен → сохранён → потреблён), либо его нет. «Модель в питоне есть, хук потом» запрещён.

### In
- kind в реестре границ
- stop/validate не пропускает «поисковый / вспомогательный»
- malformed / unknown id → fail-closed
- parent читает typed результат, не прозу

### Out
ownership mismatch семантика · сам агент+prompt соседней оси · duplicate hooks · finish journal

### Done when
1. валидный документ этого kind проходит общий validate
2. отсутствие ветки stop для managed kind = дыра, не «потом»
3. unit model_validate без e2e границы не считается закрытием

### Forbidden after
льготный вход · free-text inventory как SoT · unknown schema_id на валидном payload

### Chat decisions
- leftover runtime pipeline: модель есть, registry+stop нет
- если agent managed — pipeline обязателен

---

## Covering

### Outcome
Оркестрация не имеет права выглядеть зелёной, если контракт не исполняется. Документ без типа, тип без конвейера, payload без тела, finish без транзакции, pack без маршрута — не успех.

### Axes
- заявленный skill-path существует
- заявленный machine-тип проходит тот же конвейер
- pack не ok, если маршрут/verify неисполняемы
- один хук на realpath; runtime читает свой entrypoint
- документ своего полёта — единственный SoT решения
- ok=true только на целом исполняемом графе
- смена фазы — одна восстановимая транзакция
- материализованная политика ≡ источнику или fail-closed

### Invariants
- слой описания не считается runtime
- новый kind / pack / hook / schema без льготного входа
- ошибка формы ≠ ошибка смысла ≠ чужой полёт
- leftover старого эпика = новый ID

### Out
закрывать соседний leftover вне нарезки · REFLECT-тесты этим batch · MCP-only finish · generated README encyclopedia

### Done when
1. по каждой оси нельзя получить ok/PASS/done обходом
2. эпик не закрывает соседнюю ось «заодно»
3. Covering не отправляет агента читать чужие plan

### Forbidden after
mega-plan · presence-only parity · partial bundle как ok · prose/payload как SoT · этот Covering как SoT REPLAN · читать соседние plan

### Chat decisions
- Аудит 2026-09-05 = вход; цель = исполняемые эпики
- незакрытый соседний leftover — вне этой нарезки
- Prompt абстрактнее plan: иначе IMPLEMENT повторит известные места
