# Scoped workflow prompt builder

Дата: 2026-09-05

## Цель

Сделать сборку prompt детерминированной и узкой: первой строкой должен идти
конкретный role command текущего запуска (`BACK IMPLEMENT`, `FRONT QA`,
`INTEG DECOMPOSE` и т. п.), после него — только инструкции и контекст этого
command/шага. Это устраняет ситуацию, когда агент получает общий список ролей
и не понимает, какую workflow-ветку нужно выполнять.

## Ограничения

- `CLAUDE.md` и `AGENTS.md` не изменять.
- Не возвращать runtime chain/ledger и не загружать workflow-файлы автоматически
  через runner. Builder должен декларативно указывать текущий workflow-файл и
  обязательное чтение связанных ссылок; фактическое чтение остаётся действием
  агента.
- Не менять lifecycle/finish safety gates. Отдельно сохраняется правило, что
  отсутствие чтения не блокирует завершение задачи.
- Не включать в scoped prompt данные других ролей, фаз или workflow pack
  command prefixes.

## Дизайн

### 1. Вынести определение scope в `loop/prompt_builder.py`

Добавить чистый переиспользуемый builder с `PromptScope`, который:

- принимает `cwd`, optional explicit command и projection/state;
- нормализует команду в `ROLE PHASE`, включая `INTEGRATION → INTEG`;
- разрешает workflow pack через существующий registry/router и получает ровно
  один `rules_mdc_rel` для текущей команды;
- возвращает текущие role, phase, step, epic и диагностические данные без
  чтения содержимого workflow;
- рендерит command-first блок с HARD-правилом: прочитать `CLAUDE.md`,
  `AGENTS.md`, текущий workflow и все связанные с ним ссылки/команды; прочие
  role/phase инструкции в этот scope не входят.

При отсутствии достаточных данных builder выдаёт безопасный `UNKNOWN` scope,
а для совместимости с активным loop без phase использует `BACK IMPLEMENT` как
минимальный fallback. Ошибка разрешения pack не должна падать prompt.

### 2. Подключить scope к `loop/context_loop.py`

- Расширить `build_prompt(..., command=None)` и поставить отрендеренный scope
  до строки «Выполни один шаг».
- Использовать scope как единый источник role/phase/workflow для prompt.
- Убрать best-effort discovery всех decompose indexes при пустом `load_now`.
  Допустим текущий `armed_decompose`, если он явно указан состоянием; для
  повреждённого context возможен только однозначный fallback с единственным
  найденным индексом. При неоднозначности unrelated epics не попадают в prompt.
- Сохранить существующие phase-specific блоки, но исправить hard-coded
  `BACK BUGFIX` в QA-инструкции на текущую роль.
- Для неизвестных/custom phase не выдавать implement-specific finish rules;
  использовать короткий общий finish-блок текущего command.
- В `prepare_session` вычислять scope один раз до записи prompt, передавать
  explicit command в builder и возвращать в JSON `prompt_command` и
  `workflow_file` для диагностики/runner UI.

### 3. Сузить SessionStart context в `harness/hooks/epic/core.py`

Использовать тот же builder для `session_start_payload`:

- command-first scope становится первым блоком additional context;
- оставить fingerprint и только `load_now` bundle текущей сессии;
- убрать общий `Pack: ... | Prefixes: [...]` список всех команд;
- при ошибке pack показать короткую диагностику, не ломая запуск и не
  добавляя чужие workflow.

### 4. Тесты

Добавить `loop/tests/test_prompt_builder.py` для нормализации команд,
workflow routing, fallback и command-first HARD scope.

Расширить существующие тесты prompt/session start:

- `loop/tests/test_next_prompt.py` — command идёт первым, выбран только один
  role workflow, custom phase не получает implement finish;
- `loop/tests/test_context_loop.py` — `prepare_session` возвращает scope
  metadata и пустой `load_now` не раскрывает другие decompose indexes;
- `harness/hooks/tests/test_session_start_inject.py` и
  `loop/tests/test_workflow_pack_phase_router.py` — scoped additional context,
  отсутствие prefixes и fail-safe диагностика.

Проверка:

1. `bin/pytest -q loop/tests/test_prompt_builder.py loop/tests/test_next_prompt.py harness/hooks/tests/test_session_start_inject.py loop/tests/test_workflow_pack_phase_router.py`
2. `bin/pytest -q loop/tests/test_context_loop.py loop/tests/test_stop_gate.py`
3. `bin/pytest -q`
