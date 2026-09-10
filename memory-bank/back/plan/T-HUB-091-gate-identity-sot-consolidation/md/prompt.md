## Epic

### Outcome
Одна замороженная gate-identity правда управляет inject в child и проверкой fence на stop для Claude и Codex: агент больше не «угадывает» step/epic/session, а конфликтующие writers не ломают ownership mid-session.

### In
- Единый SoT freeze/read/bind/assert для gate identity
- Доставка SoT в child до работы (Claude inject / Codex spawn rewrite)
- Политика stop: Claude strict, Codex transport-bind из SoT
- Атомарные freeze+mirror и spawn mark+bind
- Purge поштучного coerce и ложной post-wait inject-симметрии

### Out
- DSH adapter и DSH parity
- SessionStart COMMAND / PromptScope lock как отдельный слой
- Mega hook-dispatcher и Python supervisor cutover
- Подписанные envelope / полный event projector

### Done when
1. Ownership читается только из SoT; live armed/projection после finish той же сессии не подменяет fence step.
2. Claude с чужим step получает ownership NEED_HUMAN; Codex с чужим step не получает ownership NEED_HUMAN — identity := SoT.
3. Поштучный coerce в stop нельзя использовать: остаётся один API policy.

### Forbidden after
dual-path coerce+bind · spawn-gate как независимая правда · post-wait start как Codex inject · DSH «заодно» · PromptScope как второй GateIdentity SoT

### Chat decisions
- DSH не включать в эпик
- Сократить источники правды; не размазывать конфликтующее состояние
- Атомарные операции где возможно
- Общая политика SoT + адаптеры Claude/Codex; убрать кусковой coerce как фичу
- Codex: spawn rewrite и/или жёсткая запись identity из SoT на stop (не угадайка LLM)

---

## Covering

n/a — single epic
