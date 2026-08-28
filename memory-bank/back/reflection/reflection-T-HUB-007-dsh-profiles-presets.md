---
schema: epic-reflect/v1
epic_id: T-HUB-007-dsh-profiles-presets
task_id: T-HUB-007
date: "2026-08-28"
author: gpt
verdict: PASS
---

# Ретроспектива эпика T-HUB-007-dsh-profiles-presets

## Итог

Эпик добавил полный локальный DSH-контур для восьми loop-фаз: синхронизацию prompt-пресетов из `.claude/agents/{verify,reviewer,explorer}.md`, profile manifests и Cordis patches, phase-specific model bridges, shared `dsh-phase-models` bundle, installer в `$DSH_HOME`, документацию и phase→profile mapping в `prepare_session`. Профили `epic-implement`, `epic-qa`, `epic-decompose`, `epic-plan`, `epic-creative`, `epic-audit`, `epic-bugfix` и `epic-reflect` установлены и bootable через `--dump-config`.

После первоначального аудита с одним высоким отклонением s07 исправил реальное подключение `dsh/patches/phase-models.yml`: вместо комментарийного упоминания используется поддерживаемый DSH package bundle `dsh-phase-models`, который объявлен зависимостью и первым фазовым bundle во всех восьми profiles. Повторный BACK QA завершён с `verdict: pass`, `issues: []`, `blockers: []` и пустым `fix_plan`; `@reviewer` вернул `VERDICT: PASS`.

Все s01–s07 имеют `status: completed` в decompose index. Полный parent suite прошёл: 7705 passed, 181 skipped, 48 warnings. Targeted DSH regression suite прошёл: 53 passed. Installer в чистом временном `DSH_HOME` установил ровно восемь профилей и восемь локальных `dsh-phase-models` modules; все восемь `dump-config` smoke завершились успешно. Эта REFLECT-сессия не меняла product code: `code_changed: no`.

Границы остаются явными: реальный внешний DSH API/network не запускался, проверялся локальный loader и `--dump-config`; enforcement spawn-hard и Claude Code hooks остаются в T-HUB-008 и T-HUB-016. В hub checkout `.venv/bin/graphify` и root `graphify-out/graph.json` отсутствуют, поэтому применён предусмотренный inventory fallback.

## vs plan / decompose

| Требование / outcome | Покрытие | Статус |
|---|---|---|
| FR-1: `epic-implement` package и Cordis patch | s02 | ✅ |
| FR-2: полный набор из восьми phase profiles | s02–s04 | ✅ |
| FR-3: gate presets verify/reviewer/explorer в нужных profiles | s01–s04 | ✅ |
| FR-4: copy/link installer в `$DSH_HOME/profiles` | s05 + bugfix remediation | ✅ |
| FR-5: `prepare` эмитит phase-derived `dsh_profile` | s06 | ✅ |
| FR-6: frontmatter strip и генерация prompt presets | s01 | ✅ |
| FR-7: `PROJECT_LOOP_*_MODEL` → patch mapping в README | s05 | ✅ |
| FR-8: `epic-implement --dump-config` smoke | s02 + QA | ✅ |
| FR-9: shared `phase-models.yml` реально подключён профилями | s07 + QA | ✅ |
| NFR-1: prompt bytes отслеживают agent markdown | s01, s06, s07 | ✅ |
| NFR-2: secrets отсутствуют, credentials остаются в DSH path | s02–s05 + QA integration check | ✅ |
| NFR-3: profiles boot без hub product code | s02–s05 + clean-home smoke | ✅ |
| NFR-4: pinned DSH developer-preview note | s05 + README review | ✅ |
| AC+1: installer создаёт `epic-implement` | s05 + clean-home smoke | ✅ |
| AC+2: verify/reviewer/explorer prompt bodies синхронизированы | s01, s03, s06 | ✅ |
| AC+3: `dump-config` показывает verify preset | s02 + QA | ✅ |
| AC+4: `IMPLEMENT` → `epic-implement` | s06 | ✅ |
| AC+5: README содержит все восемь фаз | s05 | ✅ |
| AC+6: model env bridge документирован | s05 | ✅ |
| AC−1: spawn-hard enforcement не дублируется | scope boundary T-HUB-008/T-HUB-016 + QA | ✅ |
| AC−2: `.claude/agents/*.md` не изменяются как source | s01/s06 + QA | ✅ |
| AC−3: Claude default loop не требует DSH | s06 + runtime regression | ✅ |
| AC−4: API keys не коммитятся | s02–s05 + QA | ✅ |
| Replacement cleanup: stub profiles заменены рабочим набором | s02, s04, s05 | ✅ |

Плановая последовательность была расширена remediation-шагом s07 после AUDIT. Это не изменило исходный outcome: оно закрыло executable include gap, сохранив локальные phase-specific bridges как финальный profile layer. Оставшихся `not_implemented[]`, `legacy_surfaces_remaining[]` и `fallback_remaining[]` нет.

## Successes

- Синхронизация presets оставила `.claude/agents/*.md` source of truth и добавила проверяемый `--check`, вместо ручного копирования prompt-текстов.
- s07 проверил реальный DSH loader contract: profiles используют ordered package bundles, а shared patch применяется до profile-local patch. Это безопаснее и точнее, чем неподдерживаемые `include/import/extends`-ключи.
- Clean temporary `DSH_HOME` smoke выявил и затем подтвердил исправление installer dependency path: теперь `$DSH_HOME/patches` и локальный `dsh-phase-models` provisioned до запуска профилей.
- Табличная phase mapping coverage и targeted regression закрепили все восемь фаз, default `IMPLEMENT` и Claude-runtime guard.
- README одновременно документирует phase matrix, env bridge, installation, dry-run/link режимы, credentials boundary и pinned preview dependency.
- QA включил не только содержимое файлов, но и executable proof: install, dependency resolution, восемь `dump-config` и полную регрессию.
- Reviewer gate прошёл без scoped defects; финальный QA artifact честно отделяет подтверждённые smoke от ограничений внешнего DSH API.

## Problems

- Первоначальный AUDIT нашёл high deviation: `phase-models.yml` существовал, но profiles только комментировали его и фактически дублировали rows локально. Потребовался отдельный s07, чтобы перейти от декларативного обещания к executable bundle.
- Первый QA проход обнаружил ошибку установки в чистый `DSH_HOME`: profile directory копировался, но `file:../../patches` и `dsh-phase-models` не provisioned. Исправление потребовало повторного BUGFIX/QA цикла.
- Event timeline содержит три `bugfix_done` и два `qa_fail` до `qa_pass`; это отражает реальный progress, но не даёт компактной machine-readable причины каждого QA remediation цикла.
- `events.jsonl` не содержит `implement_done` для s01–s07, хотя implement YAML и delivery evidence присутствуют.
- Runtime snapshot после завершения содержит `state_rebuilt: true`; `last-session.json` хранит предыдущую фазу `BUGFIX` и `retry_count: 1`, тогда как текущий checkpoint уже находится в `REFLECT` с `retry_count: 0`. Это не product failure, но снижает диагностическую ясность.
- Рабочее дерево содержит pre-existing изменения вне scope, включая `.claude/agents/explorer.md`; scoped QA/reviewer проверили T-HUB-007 без критичных дефектов, но ownership boundary приходится подтверждать вручную.
- Graphify недоступен в hub checkout. Для этого tooling-only репозитория применён ожидаемый inventory fallback; graph update не выполнялся.

## Lessons

1. Shared configuration должен иметь executable loader proof. Наличие файла и комментария в profile patch не подтверждает, что runtime его потребляет.
2. Для installer-поверхности smoke в чистом `$DSH_HOME` важнее проверки в уже загрязнённом developer home: только clean install выявляет относительные `file:` paths и missing local bundles.
3. DSH profile bundles следует проверять как ordered dependency contract: shared layer должен загружаться до phase-local override, а phase-specific env bridge должен оставаться видимым.
4. Для tooling-эпика полезно разделять source-sync tests, config shape tests, loader smoke и полный suite; один `dump-config` не покрывает installation lifecycle.
5. QA failure должен возвращаться в owning BUGFIX с bounded fix plan, а повторный QA обязан повторять clean-home и integration checks, а не только targeted unit tests.
6. Event log и runtime snapshots являются отдельным качеством оркестрации: PASS продукта не устраняет необходимость различать advance, retry, stale snapshot и rebuild.
7. Pre-existing dirty files в hub требуют scope/ownership summary до QA, иначе успешный scoped verdict труднее аудировать.

## Improvements

- Добавить `implement_done` emission в `finalize-step` для каждого sNN либо одного batch-события с перечислением шагов.
- Добавить в loop diagnostics отдельные поля для `qa_fail → bugfix_done → qa_pass`, retry без advance, stale `step_id` и `state_rebuilt`; не смешивать их в одном `retry_count`.
- Сделать clean-home installer smoke обязательным pre-QA checkpoint для profile/bundle эпиков, включая проверку локальных `node_modules` и всех phase `dump-config`.
- Добавить ownership/scope summary для dirty working tree в BACK QA recipe, особенно для hub multi-epic work.
- Закрепить post-suite assertion, что runtime snapshot не сохраняет временный pytest path и что текущие `phase`, `step_id` и `epic` согласованы.
- Добавить visible graphify preflight для обычных code-эпиков; для hub-only REFLECT оставить N/A inventory fallback без блокировки.

## Orchestration signals

| Источник | Наблюдение | Интерпретация |
|---|---|---|
| `memory-bank/back/events/T-HUB-007-dsh-profiles-presets/events.jsonl` | 7 событий: `audit_done`; `qa_fail` seq2; `bugfix_done` seq3–5; `qa_fail` seq6; `qa_pass` seq7 | Были реальные remediation cycles с advance; бесконечного same-step loop нет |
| `checkpoint.json` | Текущий `REFLECT`, `retry_count: 0`, `status: active`, fingerprint stall 0 | Текущая сессия продвинулась к REFLECT без stall |
| `state.json` | `phase: REFLECT`, `state_rebuilt: true`, diagnostic `state_rebuilt`, `halt_reason: null` | Контекст был восстановлен; это наблюдаемость, не дефект эпика |
| `last-session.json` | clean exit, `exit_code: 0`, `abort_kind: null`, `resume_dirty: false`, предыдущий `step_id: BUGFIX`, `retry_count: 1` | Один retry и stale предыдущий step snapshot; внешнего abort/halt не зафиксировано |
| `runtime/dev-hub/epic/session-2.log` | Bounded scan по abort/halt/FINISH/same-step/retry нашёл финальный QA report, но не отдельный abort/halt loop | Полный dump в reflection не переносился; явного зацикливания не обнаружено |
| Role/phase path | BACK IMPLEMENT → AUDIT remediation → QA/BUGFIX → QA PASS → BACK REFLECT | Role drift и пропуск обязательного QA не обнаружены |
| Dirty ownership | Scoped QA зафиксировал pre-existing changes вне T-HUB-007, включая explorer agent; критичных scoped defects нет | Нужен ownership summary, но текущий PASS не переоткрывается |
| Graphify | Hub checkout без root graph.json и `.venv/bin/graphify`; QA использовал bounded inventory | Ожидаемое tooling limitation, не blocker |
| External DSH API | Проверен локальный DSH loader и dump-config, внешний network/API не запускался | Ограничение текущего scope, не незакрытый AC |

**Вывод layer B:** путь эпика завершён с PASS. QA failures и bugfix cycles были конечными и привели к рабочему clean-home outcome; признаков бесконечного retry, role drift, halt или same-step stall нет. Остаются orchestration-quality сигналы: неполный event timeline, stale/rebuilt runtime snapshots и отсутствие автоматического ownership summary.

## Promote candidates

| Сигнал | → | Решение |
|---|---|---|
| Нет `implement_done` в event log | → loop/hooks | Emit на `finalize-step`; текущую историю задним числом не переписывать |
| `qa_fail`/`bugfix_done` не имеют компактной причины и progress marker | → loop/hooks | Добавить structured remediation reason и advance classification |
| `state_rebuilt: true`, stale `BUGFIX` и разный retry count в snapshots | → loop/hooks | Синхронизировать snapshot phase/step и разделить retry/rebuild diagnostics |
| Clean-home installer failure обнаружен поздно | → workflow | Сделать clean install + все phase dump-config обязательным pre-QA gate для DSH profiles |
| Pre-existing dirty files чужих эпиков | → workflow | Добавить changed-file ownership summary до QA/reviewer |
| Graphify отсутствует в hub checkout | → skip | Оставить предусмотренный N/A inventory fallback; не блокировать tooling REFLECT |
| Реальный внешний DSH API/network не входит в scope | → skip | Локальный loader/dump-config достаточен для текущего profile packaging эпика |
| Нет frontend surface | → skip | Vitest/Playwright и frontend QA к BACK tooling scope неприменимы |
| Все actionable findings и fallback surfaces закрыты | → skip | Не создавать новый implement shard; эпик готов к EPIC_DONE и ручной ARCHIVE вне loop |

## Метрики

- Шагов: 7 / 7 completed (100%).
- Audit: первоначально 6 implemented и 1 high deviation; remediation s07 закрыла отклонение.
- QA: `verdict: pass`; issues 0; blockers 0; fix_plan 0.
- Full suite: 7705 passed, 181 skipped, 48 warnings.
- Targeted DSH suite: 53 passed.
- Event log: 7 событий — 1 `audit_done`, 2 `qa_fail`, 3 `bugfix_done`, 1 `qa_pass`.
- Runtime: current checkpoint `retry_count: 0`, fingerprint stall 0; last-session `retry_count: 1`, `state_rebuilt: true`.
- Frontend tests: неприменимы.
- Graphify: N/A для hub checkout.
- `code_changed` этой REFLECT-сессии: no.

## Next

- Эпик завершён; после handoff фиксируется отдельная строка `EPIC_DONE`.
- Ручная архивация артефактов допускается только вне текущего loop после его остановки.
- Следующая отдельная команда после stop runner: `BACK ARCHIVE NOW` для T-HUB-007.
- Отложено: implement event emission, runtime retry/abort diagnostics, snapshot synchronization, ownership summary и clean-home pre-QA template; они не блокируют текущий PASS.
