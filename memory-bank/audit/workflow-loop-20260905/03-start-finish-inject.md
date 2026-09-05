# 03. Аудит start / inject / finish функций

## 1. Фактический start path

```text
runtime SessionStart
  → harness/hooks/session-start.py
  → product_cwd(payload.cwd)
  → _check_preflight_drift() [только Codex, warning]
  → epic_lib.session_start_payload()
  → load_epic_state()
  → projection + activeContext fallback
  → prompt_builder.build_prompt_scope()
  → render_prompt_scope()
  → loop.mb_load.session.load_session()
  → additionalContext + sessionTitle
```

`prompt_builder` намеренно не читает workflow files. Это правильная идея для экономии контекста: builder выдаёт только command/role/phase/step/epic/runtime и направляет agent к canonical rule chain.

## 2. P1 — runtime теряется при inject

`session_start_payload()` вызывает `build_prompt_scope()` без аргумента `runtime`. У `build_prompt_scope()` default — `claude-code`, значит `PromptScope.entrypoint` становится `CLAUDE.md`, даже когда внешний hook работает в Codex.

Это особенно опасно вместе с `mainrule.mdc`, который отдельно требует читать `CLAUDE.md`. В итоге Codex может получить и прочитать не свой runtime entrypoint.

Исправление:

```python
runtime = os.environ.get("EPIC_RUNTIME")
scope = build_prompt_scope(..., runtime=runtime)
```

Также добавить test:

```text
EPIC_RUNTIME=codex + session_start_payload → entrypoint=AGENTS.md
EPIC_RUNTIME=claude + session_start_payload → entrypoint=CLAUDE.md
```

## 3. P1 — частичный load_now считается успешным

В `loop/mb_load/session.py` missing/read errors добавляются в `diagnostic_codes`, но `ok_status` после чтения снова устанавливается в `True`. Поэтому возможен результат:

```text
ok=true
files=[часть bundle]
diagnostic_codes=[missing_file:...]
```

MCP wrapper отдельно исправляет случай `not res.files and missing_file`, но не случай частично отсутствующего bundle. `SessionStart` при `res.ok` inject-ит fingerprint и список/содержимое оставшихся файлов.

Для context boundary это false success: agent не знает, что обязательный файл отсутствует, либо видит только warning, который может быть проигнорирован.

Рекомендуемая политика:

- `ok=true` только если все обязательные `load_now` entries разрешены и прочитаны;
- optional/skipped файлы должны быть явно отмечены `optional=true` в typed request;
- результат должен содержать `required_missing`, `optional_missing`, `forbidden_skipped` отдельно;
- SessionStart при `required_missing` должен fail-closed или inject-ить `CONTEXT_INCOMPLETE` с запретом основной работы;
- не чинить это условным warning в hook-е.

## 4. P1 — SessionStart проглатывает исключения

`session_start_payload()` ловит `Exception` и добавляет в prompt строку `Warning: load_session exception (...)`. `_check_preflight_drift()` также ловит любой exception и молча продолжает.

Для неважного telemetry warning это приемлемо. Для контекстного boundary — нет. Нужно разделить:

```text
diagnostic-only → warning
required context unavailable → halt / explicit degraded mode
runtime drift → block before agent session, если runtime declared strict
```

Пользователь должен видеть код причины (`context_bundle_missing`, `runtime_sync_failed`), а не только exception text.

## 5. Контекстная экономия: что оставить и что изменить

Сейчас inline contents добавляются только если aggregate size ≤16 KiB; иначе добавляются только paths. Это хорошо как bounded inject, но не хватает:

- обязательности каждого path;
- размера/sha/truncated metadata в rendered context;
- версии bundle и pack id;
- явной маркировки optional file;
- проверки, что fingerprint относится именно к тому activeContext, который был прочитан.

Предлагаемый формат:

```text
CONTEXT_BUNDLE id=<uuid> fingerprint=<sha256> status=complete|incomplete
required: path sha size
optional: path sha size
```

Inline body оставлять только для маленьких required files; большие файлы читать targeted tool-ом по path после успешной проверки bundle.

## 6. Полный finish path

```text
prepare_session()
  → activeContext/state/pack/checkpoint/integrity checks
  → prompt file
  → agent session
  → SubagentStop verdict/repair hooks
  → check_after()
  → halt_logic.decide_after_action()
  → mb-finish <phase>
  → render_active_context()
  → atomic activeContext write
  → finalize_step() [для implement]
  → index/status/event/portfolio sync
  → next Handoff / DONE
```

Сейчас `check-after` правильно возвращает `halt=true`, CLI возвращает rc=1, а `loop.sh` различает `continue`, `complete`, `halt`. Это исправление из прошлых проблем нужно сохранить.

## 7. P1 — activeContext и index/state не являются одной транзакцией

`finish_implement_step()`:

1. читает backup activeContext;
2. пишет новый activeContext;
3. вызывает `finalize_step()` для implement/index/state;
4. при ошибке пытается восстановить activeContext.

Это защищает обычный error path, но не crash между пунктами 2 и 3. В таком окне activeContext уже содержит новый Handoff, а index/state могут остаться прежними. Atomic write гарантирует целый файл, но не atomic multi-file commit.

Усилить через checkpoint transaction:

```text
prepare transaction id
  → write staged activeContext/index/state
  → validate all staged artifacts + identity
  → commit marker
  → replace all files
  → recovery on next prepare
```

Минимальный вариант: persistent `finish_transaction/v1` journal с `prepared`, `context_written`, `index_written`, `committed`, `rollback_required`; `prepare_session()` должен уметь завершить или откатить transaction.

## 8. P1 — `finish_handoff()` обходной путь слишком мощный

`loop/mb_finish/impl.py:finish_handoff()` прямо рендерит и пишет activeContext, а затем вручную меняет `armed_step/phase/active/status`. Это документировано как low-level escape hatch, но он не выполняет полный verify/finalize contract.

Риски:

- можно перевооружить workflow, не записав artifact/index transition;
- state может стать `armed`, хотя finish gate не прошёл;
- разные callers получают неодинаковую гарантию атомарности.

Рекомендация: оставить внутренний primitive только для recovery, закрыть публичный CLI route или требовать explicit `recovery_token`/`repair_mode` и журналировать его. Обычные workflow должны вызывать phase-specific typed finish command, который проходит единый transaction service.

## 9. P1 — save state: atomic не равно lost-update safe

`save_state()` для spawn-gate использует lockfile. `save_epic_state()` использует atomic replacement, но не отдельный read-modify-write lock. Два hook-а могут одновременно загрузить один state, изменить разные поля и последний overwrite потеряет изменение первого.

Нужно использовать один lock/transaction primitive для:

- epic state;
- gate sidecars;
- activeContext + index transition;
- incident state, если он участвует в stop decision.

## 10. P1 — текущий REFLECT transition частично удалён

В dirty worktree удалены reflection helpers и exports из `harness/hooks/epic/core.py`, но `loop/mb_finish/impl.py` и MCP dispatch всё ещё содержат `finish_reflect`. Это не просто устаревшая документация: вызывает `ImportError`.

Нужно выбрать завершённую миграцию:

- удалить REFLECT из phase registry, finish dispatch, schemas/handlers, tests, docs, generated prompts и state migration;
- либо временно восстановить все exports и завершить удаление отдельным atomic migration.

Нельзя оставлять “частично работает” между start/finish transitions.

## 11. Рекомендуемая архитектура start/finish

Вместо разрозненных функций ввести:

```text
ContextBoundaryService
  load_required_bundle(expected_context) -> ContextBundle
  validate_bundle(bundle) -> complete/incomplete

TransitionService
  prepare(expected_identity)
  record_evidence
  validate_handoff
  commit_transition
  recover_transaction
```

Hooks и CLI должны быть тонкими adapters. Тогда основной invariant не будет повторяться в `session_start_payload`, `check_after`, `finish_handoff`, `finish_qa`, `finish_bugfix` и `finish_implement_step`.
