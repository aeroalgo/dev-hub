# clarify — stack-profiles-rust-python-js

**plan_id:** n/a  
**slug:** stack-profiles-rust-python-js  
**role:** back  
**date:** 2026-09-06  
**feature_description:** Внутренний контракт профилей стеков, через который workflow получает операции проекта без жёсткой привязки к Python, Rust или JavaScript.
**status:** done

---

## Контекст и цель

- Вход: пользователь просит спланировать поддержку Rust вместе с Python и JavaScript; предыдущий контекст фиксирует цель убрать stack-specific хардкод из workflow и дать изолированные контракты навыкам.
- Цель Phase 0: определить минимальный шипуемый scope и границу между workflow, stack profile и будущей подключаемой skill.
- Ограничения: это brownfield dev-hub; нельзя подменять внутренний `bin/pytest` самого хаба командами управляемого проекта; arbitrary shell-плагины и внешний marketplace не предполагаются без отдельного решения.

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Нужны не «три набора команд», а единая безопасная граница: workflow заявляет намерение, а выбранный профиль проекта детерминированно разрешает его в инструменты и аргументы конкретного стека. Это уменьшает дрейф между Rust/Python/JS и оставляет навыки независимыми от языка. |
| **Premises** | 1. `accepted` — Python, Rust и JS имеют общие жизненные операции (проверка, тест, сборка), хотя команды различаются. 2. `accepted` — hub и целевой проект — разные контексты; тесты самого hub остаются на его Python-каноне. 3. `challenged` — «подключаемые skills» требуют общего плагин-маркета уже в v1. 4. `deferred` — JS toolchain и package manager можно выбрать без влияния на публичный контракт. 5. `accepted` — неизвестный профиль или capability должны завершаться fail-closed, а не fallback к Python-команде. |
| **Weakest link** | Если v1 не ограничить декларативным профилем и фиксированным словарём capabilities, она превратится в исполнение произвольных shell-команд под видом универсального API. |
| **Anti-scope** | Не строим marketplace, удалённую установку skills, произвольные shell hooks, миграцию всех нынешних layout-путей и поддержку всех языков мира в первой поставке. |
| **Verdict** | `needs_user_Q` |

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Partial | Нужен выбор минимального v1: профили команд или также динамические skills/workflows. |
| data | Partial | Нужны схема профиля, capability vocabulary и правило выбора профиля проектом. |
| UX-API | Partial | CLI/API вызова capability и диагностический контракт ещё не определены. |
| NFR | Partial | Fail-closed и детерминизм очевидны; версии инструментов, timeout и sandbox надо определить. |
| integrations | Partial | Rust/Cargo известен; Python и JS toolchain требуют декларации профилем. |
| edge | Partial | Unknown profile/capability, отсутствующий binary, конфликт manifest'ов, monorepo. |
| constraints | Clear | Внутренний dev-hub, Rust + Python + JavaScript, без замены внутренних тестов хаба. |
| terminology | Partial | Нужно зафиксировать значения profile, capability, workflow request и skill requirement. |

---

## Q→A log

### Q1

- **Question:** Какой минимальный результат v1 должен дать этот эпик?
- **Why it matters:** выбор задаёт публичную границу, нарезку эпиков и не позволяет смешать безопасный профиль стека с полноценной платформой плагинов.
- **Recommended:** A — сначала контракт stack profile + resolver для трёх стеков; skills и workflow только потребляют capabilities, но не загружаются динамически.
- **Options:**
  - **A. Профили и capabilities** — декларативные локальные профили Python/Rust/JS; workflow запрашивает фиксированную capability (`test`, `lint`, `format`, `build`), resolver возвращает проверенный argv и fail-closed ошибку.
  - **B. Сразу plugin platform** — плюс регистрация/обнаружение сторонних skills и workflow-пакетов в первом эпике.
  - **C. Только алиасы команд** — единый фасад для `pytest`/`cargo`/`npm`, без manifest-схемы и выбора профиля проектом.
- **Answer:** A — профили и capabilities.
- **resolution:** resolved. V1 ограничен декларативными локальными профилями Python/Rust/JS; workflow и skills потребляют фиксированный vocabulary capabilities. Динамическая регистрация сторонних skills/workflow-packages и shell-alias-only подход не входят в эпик.

### Q2

- **Question:** Как JavaScript-профиль v1 должен выбирать package manager и команды проекта?
- **Why it matters:** `npm`, `pnpm`, `yarn` и `bun` имеют разные lockfiles, invocation и способы запуска scripts; хардкод одного менеджера снова сделает контракт негибким.
- **Recommended:** A — auto-detect по единственному lockfile, а при конфликте или отсутствии lockfile требовать явный выбор в project manifest и завершаться fail-closed.
- **Options:**
  - **A. Lockfile-first + явный override** — распознавать `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock` или `bun.lock*`; конфликт/отсутствие → diagnostic, пока project manifest явно не выберет manager.
  - **B. Только pnpm** — JavaScript v1 поддерживает исключительно pnpm независимо от репозитория.
  - **C. Только явная настройка** — не делать auto-detect; каждый JS-проект обязан назвать manager в manifest.
- **Answer:** ожидается.
- **Answer:** A — lockfile-first + явный override.
- **resolution:** resolved. JS resolver распознаёт единственный поддерживаемый lockfile; несколько или ни одного lockfile дают fail-closed diagnostic до явного выбора package manager в project manifest. Нельзя молча выбрать `npm` или `pnpm`.

### Q3

- **Question:** Где проект явно назначает stack profile и его override-параметры?
- **Why it matters:** существующий `.dev-hub` уже служит маркером/ссылкой на hub; переиспользование его как конфигурации смешает discovery хаба с контрактом целевого проекта и создаст конфликт путей.
- **Recommended:** A — отдельный корневой `dev-hub.project.yaml`; doctor/init может предложить его из детектированных файлов, но runtime читает только этот manifest и не угадывает профиль.
- **Options:**
  - **A. Отдельный project manifest** — `dev-hub.project.yaml` в корне управляемого проекта содержит `profile`, optional JS manager override и безопасные capability overrides; `.dev-hub` остаётся только link/discovery marker hub.
  - **B. Расширить `.dev-hub`** — заменить текущий одноцелевой marker структурированной конфигурацией профиля и пути к hub.
  - **C. Только автоопределение** — profile выбирается по `pyproject.toml` / `Cargo.toml` / `package.json`, без явного manifest.
- **Answer:** ожидается.
- **Answer:** A — отдельный project manifest.
- **resolution:** resolved. `dev-hub.project.yaml` — единственный явный SoT назначения stack profile и overrides; `.dev-hub` сохраняет прежнюю роль marker/link к hub. Автодетектор допустим лишь как рекомендация doctor/init, не как runtime fallback.

### Q4

- **Question:** Какой словарь capabilities должен войти в первый shippable contract?
- **Why it matters:** слишком узкий словарь не снимет Python-hardcode из проверок, а `run`, миграции и deploy дадут опасный произвольный execution surface до того, как профиль доказал базовую ценность.
- **Recommended:** A — только проверяемые операции качества: `format.check`, `lint`, `typecheck`, `test.targeted`, `test.full`, `build`; никаких `run`, `migrate`, `deploy` и arbitrary script capability в v1.
- **Options:**
  - **A. Verify-first vocabulary** — format/lint/typecheck/targeted+full tests/build; профили возвращают argv и requirement diagnostics для каждой операции.
  - **B. Developer workflow vocabulary** — A плюс `run.dev`, `migrate`, `generate`, позволяющий запускать локальные сервисы и генераторы.
  - **C. Минимум CI** — только `test.full` и `build`; lint/format/typecheck остаются захардкоженными или ручными.
- **Answer:** ожидается.
- **Answer:** A — verify-first vocabulary.
- **resolution:** resolved. V1 включает только `format.check`, `lint`, `typecheck`, `test.targeted`, `test.full`, `build`; `run.dev`, migrations, generation, deploy и произвольное выполнение не являются capabilities профиля.

### Q5

- **Question:** Должен ли один `dev-hub.project.yaml` v1 описывать несколько независимых targets в monorepo?
- **Why it matters:** Rust service, Python worker и JS client часто живут в разных подкаталогах; без явной модели target resolver либо ошибочно запускает команду из корня, либо вводит небезопасный поиск вложенных конфигураций.
- **Recommended:** A — manifest поддерживает именованные targets с относительным `root` и profile; один target можно пометить default, а дубли, выход за границу workspace и неявный выбор дают fail-closed diagnostic.
- **Options:**
  - **A. Явные named targets** — один manifest содержит `targets.<name>.root` и `profile`; команда выбирает target явно либо безопасный default. Вложенный discovery не нужен.
  - **B. Только один root project** — один manifest = один profile в корне; monorepo отложить отдельным эпиком.
  - **C. Каскад manifests** — resolver ищет и объединяет manifest'ы по дереву каталогов.
- **Answer:** ожидается.
- **Answer:** A — явные named targets.
- **resolution:** resolved. Один `dev-hub.project.yaml` описывает именованные targets с workspace-relative `root` и выбранным `profile`; допустим один default target. Resolver запрещает путь вне workspace, дубли root/name и неявный выбор при нескольких targets.

---

## Deferred / [НУЖНО УТОЧНИТЬ] items

| Item | Severity | Why deferred | Next |
|------|----------|--------------|------|
| Package manager и тестовый раннер JavaScript-профиля | IMPORTANT | Решается Q2. | Текущий вопрос. |
| Формат project manifest и discovery в monorepo | IMPORTANT | Решается Q3. | Текущий вопрос. |
| Policy версий бинарников и timeout | IMPORTANT | Зафиксировать в плане как fail-closed policy; не требует отдельного Q при выбранном verify-first scope. | Plan review batch. |

---

## Completion Report

- **Grill:** done · verdict=needs_user_Q · grill_Q=1
- **Asked:** 5/5
- **Resolved:** scope v1 — profiles + capabilities; JS manager — lockfile-first + explicit override; project manifest — отдельный `dev-hub.project.yaml`; vocabulary — verify-first; monorepo — explicit named targets.
- **Deferred:** policy версий бинарников и timeout — IMPORTANT, owner=BACK PLAN review batch; не блокирует контракт, потому что v1 не выполняет lifecycle/deploy capabilities.
- **Coverage:** scope=Partial · data=Partial · UX-API=Partial · NFR=Partial · integrations=Partial · edge=Partial · constraints=Clear · terminology=Partial
- **Next action:** `BACK PLAN stack-profiles-rust-python-js` Phase 1.
