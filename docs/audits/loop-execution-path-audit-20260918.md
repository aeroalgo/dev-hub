# Аудит execution loop: старые и канонические пути

Дата: 2026-09-18  
Область: `loop/`, `harness/hooks/`, workflow-правила, runtime adapters, memory-bank lifecycle, finish/recovery, board sync и episode retention.  
Основание: текущий код и документы репозитория, а также эпики T-HUB-086—T-HUB-106, которые заявляли последовательные purge/cutover-миграции.

## Итог

Текущий loop имеет рабочий канонический каркас:

`bin/loop` → `loop.runner` → runtime adapter → typed SessionStart/context → arm через `epic_transition` → работа в ограниченном контексте → checkpoint/evidence → typed verify → `finalize-step`/transaction → reducer → следующий шаг.

На старте аудита были найдены параллельные маршруты, выполнявшие ту же работу, что и новые версии. Основные live-дубли удалены последовательно; в репозитории намеренно оставлены только совместимость, human mirror и offline migration, если они ещё имеют consumers:

1. общий transaction helper ещё не заменил уже transaction-based `finish_implement/qa/bugfix`;
2. migration/MD mirror и часть исторических compatibility branches всё ещё видны в коде, но не являются каноническим lifecycle source;
3. `loop/loop.sh` сохранён как compatibility shim из-за найденных consumers;
4. широкий исторический корпус bare imports требует отдельного безопасного прохода.

Главный вывод: **лучшие решения уже присутствуют; следующий этап — не придумывать новые механизмы, а убрать дублирующие маршруты и заставить все движения loop проходить через них.**

Оценка текущего состояния: **жёлтый / conditional ready**. Фокусные regression-матрицы после очистки проходят (`327` и `329` тестов), но полный тестовый прогон в текущем dirty worktree не завершился в установленный 300-секундный лимит. Это нельзя считать полным PASS.

## Что уже доказанно лучше и должно остаться

| Участок | Каноническое решение | Почему оставить |
|---|---|---|
| Запуск | `bin/loop` → `python3 -m loop.runner` | Один Python supervisor, единая конфигурация cwd/root и единый exit contract. |
| Runtime | `loop/runtime_registry.yaml` и adapters для Claude/Codex | Runtime выбирается через registry; неизвестный runtime должен fail-closed. DSH live adapter уже удалён эпиком T-HUB-106. |
| Arm/transition | `loop.epic_transition.arm_phase` и `arm_epic` | Одна точка проверки phase registry, identity, pre/post paths и armed cursor. |
| Phase contract | `loop/schemas/phase_registry.yaml` | Typed registry вместо разрозненных `if phase == ...`; terminal phase — `DONE`. |
| Чтение контекста | `loop.mb_load.session.load_session` | Проверка shape/frontmatter, required/optional paths, size cap, sha256/fingerprint и typed diagnostics. |
| Scope | context ledger, `context_scope`, search allowlist | Read/search ограничиваются текущим shard; fingerprint делает drift видимым. |
| Запись state | typed state/checkpoint APIs и atomic writes | Runtime state не должен создаваться агентом произвольным `Write`. |
| Работа с implement | `finalize_step` + `FinishTxRecord` | Verify PASS, implement/index status и activeContext меняются в одном контролируемом finish-контуре. |
| QA/BUGFIX | `finish_qa`/`finish_bugfix` с transaction journal | Ошибка между записью handoff и state может быть восстановлена, а не замаскирована. |
| Roadmap | `memory-bank/<role>/roadmap/queue.yaml`, `roadmap-queue/v2` | YAML queue с валидацией и atomic write вместо Markdown queue mirrors. |
| Gates/evidence | typed verifier receipt, capability checks, write-deny policy | Gate подтверждается машиночитаемым evidence, а не текстом агента. |
| Abort/recovery | bounded retry + typed checkpoint + forensic episode | Повтор ограничен, incident не очищается молча, restart может продолжить с durable cursor. |
| События | event schema v2 и reducer | Lifecycle выводится из событий и артефактов, а не из случайного текста в prompt. |

## Переходы, которые уже были сделаны эпиками

Эта таблица фиксирует не просто историю, а правильное направление выбора: левый вариант должен исчезать из live execution path, правый — оставаться владельцем решения.

| Эпики | Старый путь | Лучший путь | Состояние |
|---|---|---|---|
| T-HUB-086 | shell/ручное orchestration и runtime-specific ветки | Python supervisor и registry-based adapters | Канон оставлен; остаточные imports/diagnostics перечислены отдельно. |
| T-HUB-087, 096 | v1 layout, поиск по разным именам `index.*` | layout v2 resolver, YAML index и typed shards | Основной live resolver/finish/read path переведён на YAML v2; migration mirror оставлен. |
| T-HUB-088 | локальные phase arms и разрозненные переходы | `epic_transition.arm_phase` | Канон оставлен; legacy conversion не используется как основной route. |
| T-HUB-089, 103 | разрозненные event/DAG форматы | event schema v2, DAG v2 и единый reducer | Канон оставлен; board legacy discovery удалён. |
| T-HUB-090 | compatibility launcher как равноправный entrypoint | `bin/loop` как единственный launcher | `loop/loop.sh` оставлен только как thin shim: consumers ещё найдены. |
| T-HUB-091 | gate identity из свободного текста | typed identity и verifier receipt | Оставить. |
| T-HUB-095 | несколько импортных фасадов runtime | единый canonical package/import owner | Основные hot paths переведены; исторический hook-корпус требует отдельного прохода. |
| T-HUB-097 | online/offline runtime adapter coupling | offline-safe adapter hygiene | Оставить; проверить только остаточные пути. |
| T-HUB-098, 099 | агент пишет capability/state/evidence напрямую | capability profile и Write/Bash deny policy | Оставить. |
| T-HUB-100 | повторный широкий поиск и неявный context | context fingerprint + ledger + allowlist | Оставить. |
| T-HUB-101 | очистить open incident при старте | сохранять incident до явного закрытия | Оставить; это важнее удобного, но разрушительного reset. |
| T-HUB-104 | несколько plan-path classifiers | единый layout/path resolver | Частично; board/finish всё ещё имеют собственные классификаторы. |
| T-HUB-105 | roadmap sources в plan-dir и Markdown mirrors | `roadmap/queue.yaml` v2 | Board scan использует canonical queue; legacy queue sources удалены из live scan. |
| T-HUB-106 | DSH runtime, stream filter и DSH tests | только поддерживаемые Claude/Codex paths | Live DSH adapter и stale `DSH_PATH` diagnostic удалены. |

## Инспекция каждого движения loop

### 0. Запуск loop

Лучший путь: `bin/loop` устанавливает root и запускает `python3 -m loop.runner`. `loop/loop.sh` лишь делегирует туда и не должен быть вторым контрактом.

Остаток: `loop/loop.sh` всё ещё является видимым compatibility entrypoint. Это допустимо только как короткий migration shim; если вызовов больше нет, его следует удалить вместе с тестами на shim.

### 1. Подготовка сессии и arm

Лучший путь: `context_loop.prepare_session` загружает state, строит projection, вызывает `epic_transition`, создаёт checkpoint и готовит runtime adapter.

Проблемы:

- `loop/epic_transition.py:266-297` при ошибке загрузки registry из target cwd молча пробует hub root. Для pack isolation это fail-open: можно получить валидный registry, но не тот, который принадлежит target project.
- `_arm_pre_implement` в `loop/epic_transition.py:852-902` конвертирует MD paths и продолжает рекламировать `md/decompose-index.md` как часть обычного runtime flow.
- `harness/hooks/epic_paths.py:243-296` сначала проверяет YAML, но может вернуть MD; при exception silently продолжает собственный legacy lookup.

Решение: arm должен принимать только canonical YAML index и typed step shards. MD допускается для human mirror и offline migration, но не как вход для runtime decision.

Статус после очистки: основной resolver/finish/read path использует YAML v2; MD-only вход не может продолжить lifecycle. Оставшиеся conversion/migration helpers требуют отдельного удаления после legacy-consumer sweep.

### 2. SessionStart и identity

Лучший путь уже есть в `harness/hooks/epic/core.py:1745-1882`: state + activeContext metadata + projection сравниваются через `resolve_session_identity`, а `load_session` возвращает typed result.

Проблема: при identity drift или неполном bundle hook возвращает `additionalContext` с `HALT`, но результат всё ещё может быть передан дальше runtime. Текстовая инструкция — не machine stop. Особенно опасна ветка `CONTEXT_INCOMPLETE`: агент может быть запущен с сообщением, что ему нельзя работать.

Решение: `prepare_session` должен получать typed `SessionStartResult` и не вызывать runtime adapter при `drift`, `required_missing`, shape error или incomplete required bundle. Текстовый HALT оставить только как диагностику.

Статус после очистки: `prepare_session`, `check_after` и SessionStart теперь возвращают machine-level `halt` до spawn при incomplete/invalid context; checkpoint mismatch даёт typed drift.

### 3. Чтение файлов

Лучший путь: `loop/mb_load/session.py` читает только разрешённые `load_now`, проверяет обязательные файлы, cap, sha256 и выдаёт fingerprint. План может быть path-only, а не бездумно встраиваться целиком.

Слабее текущего канона: `loop/mb_load/resolver.py` использует bare `epic_paths` import и `except Exception: pass`, после чего строит fallback `implement-{item}` paths. Это может скрыть ошибку layout и вернуть похожий, но не тот файл.

Решение: все path resolution calls перевести на один `loop.paths`/pack-aware owner; ошибки resolver возвращать как typed diagnostic, не продолжать с guessed path.

Статус после очистки: `mb_load/resolver.py` переведён на canonical imports, guessed-ID fallback и swallowed resolution exception удалены.

### 4. Чтение правил и выбор роли/mode

Лучший путь: текущий runtime entrypoint и `mainrule.mdc` → выбранная workflow chain → shard-specific files. Это лучше старого чтения всех Markdown-правил подряд: уменьшается контекст и появляется explicit scope.

Проблема: workflow corpus содержит старые REFLECT commands/rules, хотя phase registry и актуальные mainrules уже говорят, что REFLECT не является gate. Это создаёт два взаимоисключающих instruction paths.

Решение: оставить reflection только как архивный артефакт, убрать его из live mode table, parser, retry rearm и hot-path command links.

Статус после очистки: live `REFLECT` phase/commands/rules удалены; `reflection_done` и исторические reflection artifacts сохранены только для replay/archive.

### 5. Read/Edit/Write во время работы

Лучший путь: агент читает разрешённый context, а runtime state, activeContext, evidence и gate artifacts меняются через typed finish/transition APIs. `pretool_policy.py` уже запрещает прямую запись важных state paths.

Это один из самых сильных результатов эпиков T-HUB-099/T-HUB-100 и его не нужно заменять новым механизмом.

Остаточный риск: рядом существуют low-level writers в `harness/hooks/epic/core.py:4257-4297`, `loop/parallel/orchestrator.py:75` и `harness/hooks/epic/core.py:2813`. Чем больше таких writers, тем труднее доказать atomicity и ownership.

### 6. Spawn verifier/runtime и обработка обрыва

Лучший путь: registry-based adapter, bounded retries, checkpoint stages, stream log analysis и typed abort/episode record.

Остатки:

- `loop/runner/orchestrator.py:68-89` имеет dual import fallback для `epic_paths`;
- `loop/runner/orchestrator.py:494` всё ещё сообщает `DSH_PATH`, хотя DSH удалён;
- `loop/runner/orchestrator.py:557-564` проверяет hardcoded `runtime/dev-hub/epic/checkpoint.json`, который не совпадает с resolver-based project state dir и ошибки игнорирует;
- episode bundle имеет fallback на старое имя `checkpoint_snapshot.json` и местами проглатывает copy errors.

Решение: checkpoint path получать только из config/state-dir resolver; stale diagnostic и старое имя удалить после проверки исторических episode artifacts. Ошибка упаковки должна попасть в typed manifest как `partial/error`, а не исчезнуть.

Статус после очистки: runner использует `config.state_dir/checkpoint.json`, DSH diagnostic удалён, bundle записывает `artifact_status` и typed `artifact_errors`; старый snapshot filename больше не является source.

### 7. Finish

Лучший путь уже реализован для implement/QA/BUGFIX: validate → evidence → transaction journal → atomic activeContext/state commit → `finalize_step` → reducer.

Но finish surface раздвоен:

- `loop/mb_finish/mcp_server.py:17-27` публично экспортирует `finish_handoff` без `recovery_token`;
- `loop/mb_finish/impl.py:56-166` теперь намеренно запрещает tokenless вызов, поэтому MCP tool является dead/always-forbidden public route;
- `finish_decompose`, `finish_plan`, `finish_audit`, `finish_creative` в `loop/mb_finish/impl.py` используют собственные `atomic_write_text + backup`, а не общий `FinishTxRecord`;
- `harness/hooks/epic/core.py:2813` и `loop/parallel/orchestrator.py:75` пишут index YAML напрямую через `write_text`.

Решение: удалить `finish_handoff` из public MCP TOOLS; если recovery API нужен, оставить его только как internal transaction recovery с обязательным token. Все phase finishers перевести на общий transaction service. `mark_index_step_status` сделать internal writer’ом canonical finalize/repair, а не вторым finish API.

Статус после очистки: public `finish_handoff` удалён из MCP/CLI surface; четыре legacy phase finisher (`decompose/plan/audit/creative`) используют `commit_finish_context`; implement/QA/BUGFIX сохраняют свои уже transaction-based owners.

### 8. Transition после finish

Лучший путь: reducer читает typed artifacts/events, `epic_transition` выбирает следующий phase, а `activeContext` строится как projection.

Проблема: `loop/schemas/phase_registry.yaml` содержит terminal `DONE` и не содержит REFLECT, но `loop/WORKFLOW.md`, `session_resilience.py`, `epic_index.py`, `context_loop.py` и старые commands всё ещё упоминают REFLECT. `context_loop.py:3506-3550` даже включает REFLECT в retry rearm set.

Это не косметический долг: нормализованный phase может быть отвергнут registry, а workflow docs требуют недостижимый gate. Канон должен быть единым: `QA PASS → DONE`; `reflection-*.md` — только archive/non-gate.

Статус после очистки: live transition/parser/rearm path больше не содержит `REFLECT`; архивные reflection records не участвуют в выборе следующей live phase.

### 9. Roadmap/DAG/board projection

Лучший путь: queue v2 в `memory-bank/<role>/roadmap/queue.yaml`, DAG v2 и board projection из reducer.

Остатки legacy discovery:

- `loop/board_sync/scan_epics.py:69-108` ищет `roadmap-{role}.queue.yaml`, `plan-*.md`, `decompose-*` и одновременно v2 YAML;
- `loop/board_sync/scan_gates.py:174-219` ищет `plan/roadmap-epics.queue.yaml`, `roadmap-*.queue.yaml` и старые `decompose-*`;
- `loop/paths/epic_layout.py:164` считает и `decompose-index.md`, и YAML признаком discovery.

Решение: runtime board scan должен читать только canonical queue/index. Legacy paths оставить только в offline migration/fixture adapter и явно переименовать/ограничить их scope.

Статус после очистки: `scan_epics`, `scan_gates` и board path helpers используют canonical queue/index discovery; legacy queue files и flat plan globs больше не являются board sources.

### 10. Episode, incident и архив

Лучший путь: сохранять checkpoint/log/evidence, делать typed forensic manifest и не чистить open incident на старте. Это решение T-HUB-101 оставить.

Улучшить нужно поведение частичного archive: copy/retention errors не должны превращаться в успешный episode без файла. Нужен manifest с `status: complete|partial|failed`, error code и исходным path.

## Приоритетные находки

| ID | Приоритет | Находка | Доказательство | Что сделать |
|---|---:|---|---|---|
| LOOP-P0-01 | P0 | REFLECT остаётся живой веткой при registry без REFLECT | `phase_registry.yaml:8`, `context_loop.py:3506-3550`, `session_resilience.py:1343`, `WORKFLOW.md:5,10,87` | QA PASS сразу ведёт в DONE; убрать REFLECT из rearm/parser/mode table/горячих команд. Reflection artifacts оставить только архивом. |
| LOOP-P0-02 | P0 | Runtime принимает MD/v1 index routes рядом с YAML v2 | `epic_paths.py:243-296`, `epic/core.py:2146-2263`, `finish_implement.py:44-96`, `epic_transition.py:852-902` | Runtime разрешает только `yaml/decompose-index.yaml` и `yaml/steps/*.yaml`; MD и v1 имена — только offline migration. |
| LOOP-P1-03 | P1 | Pack isolation нарушается fallback target cwd → hub root | `epic_transition.py:282-292`, также `epic/core.py:887-892` | Удалить silent fallback; вернуть typed `pack_path_missing` с target path. Hub root использовать только explicit migration command. |
| LOOP-P1-04 | P1 | SessionStart может выпустить агент с текстовым HALT | `epic/core.py:1745-1882` | Машинно блокировать adapter spawn при incomplete/drift; `additionalContext` использовать только для объяснения. |
| LOOP-P1-05 | P1 | Публичный `finish_handoff` всегда запрещён token policy | `mb_finish/mcp_server.py:17-27`, `mb_finish/impl.py:56-79` | Удалить из public TOOLS; оставить private recovery API либо сделать его typed transaction endpoint с token schema. |
| LOOP-P1-06 | P1 | Finish paths имеют две модели atomicity | `mb_finish/impl.py:988,1159,1464,1614` против `FinishTxRecord` в implement/QA/BUGFIX | Объединить все finishers через один transaction/recovery service. |
| LOOP-P1-07 | P1 | После purge остаются dual imports и broad exception fallback | `runner/orchestrator.py:66-89`, `mb_load/resolver.py:89-95`, `episodes/*.py`, `roadmap_queue.py` | Выбрать один import owner/package; запретить live bare imports и `except Exception: pass` на resolution. |
| LOOP-P1-08 | P1 | Identity размазана по state, activeContext, projection и checkpoint | `prompt_builder.resolve_session_identity`, `session_start_payload`, checkpoint schema | Объявить: checkpoint — recovery authority, typed artifacts — lifecycle authority, activeContext — prompt projection, state — derived telemetry. Добавить reducer consistency check. |
| LOOP-P2-09 | P2 | Board scan продолжает legacy queue/plan discovery | `scan_epics.py:69-108`, `scan_gates.py:174-219` | Удалить live legacy glob’ы; миграцию вынести в offline command. |
| LOOP-P2-10 | P2 | Index writers обходят общий atomic owner | `epic/core.py:2813`, `parallel/orchestrator.py:75` | Один typed atomic index writer; MD mirror строить только после успешного YAML commit. |
| LOOP-P2-11 | P2 | Неверный checkpoint path и stale DSH diagnostic | `runner/orchestrator.py:494,557-564` | Использовать `config.state_dir/checkpoint.json`; удалить DSH wording и swallow ошибки. |
| LOOP-P2-12 | P2 | Episode copy/fallback может скрыть неполный forensic bundle | `episodes/bundle.py:78-121` и retention handlers | Typed partial manifest; убрать старое `checkpoint_snapshot.json` после одноразовой миграции. |
| LOOP-P2-13 | P2 | `loop/loop.sh` остаётся вторым entrypoint | `loop/loop.sh` | После поиска consumers удалить shim или оставить только в offline migration с sunset date. |

## Что удалять и что оставлять

### Оставить

- `bin/loop`, `loop.runner`, runtime registry и Claude/Codex adapters;
- `epic_transition.arm_phase`, phase registry и typed lifecycle reducer;
- `loop.mb_load.session`, context fingerprint/ledger и search allowlist;
- typed checkpoint/recovery и bounded retry;
- `FinishTxRecord`, `finalize_step`, phase-specific finish API после унификации;
- YAML queue/DAG/event/capability evidence;
- atomic writes и forensic incident retention;
- v1→v2 migration scripts, но только как offline tools, не как runtime fallback;
- YAML → MD human mirror, только если MD никогда не читается для lifecycle decision.

### Кандидаты на удаление после guard tests

- все live REFLECT phase/command/parser/rearm references;
- MD/v1 branches из runtime `find_decompose_index_path`, finish fallback lists и `epic_transition` conversion;
- legacy queue discovery в board sync;
- public MCP `finish_handoff` и незащищённые low-level handoff exports;
- dual import fallbacks, bare `sys.path` facades и `except Exception: pass` вокруг canonical resolution;
- hub-root fallback для target pack;
- hardcoded checkpoint path и DSH_PATH text;
- `loop/loop.sh`, если repository-wide call-site scan подтвердит отсутствие потребителей;
- old episode snapshot fallback после одноразовой миграции исторических bundles.

Удалять не следует:

- bounded retry/checkpoint recovery;
- explicit offline migration;
- diagnostic `HALT`, если он дополнен machine-level stop;
- archive reflection documents, пока на них есть исторические ссылки — но они должны быть исключены из live lifecycle.

## Рекомендуемый порядок исправлений

1. Устранить contradictions P0: `REFLECT` и MD/v1 runtime resolution.
2. Ввести fail-closed pack/path resolution без target→hub fallback.
3. Перед spawn превратить SessionStart incomplete/drift в machine stop.
4. Удалить public dead `finish_handoff` и перевести все finishers на единый transaction owner.
5. Убрать dual imports и старые board queue globs.
6. Исправить checkpoint path/DSH diagnostics и сделать episode partial state явным.
7. Только после этого удалить compatibility shim и старые migration aliases.
8. Добавить static guards, запрещающие появление live `REFLECT`, `index.md` decision routes, legacy queue globs и bare import fallbacks.

## Минимальные критерии перед удалением

Для каждой группы удаляемого кода нужен отдельный guard:

- `rg`/AST guard на отсутствие live REFLECT вне archive directories;
- тест: MD-only index не может arm/finish/transition;
- тест: broken target pack не загружается из hub root;
- тест: incomplete SessionStart не вызывает runtime adapter;
- тест: public tool list не содержит tokenless `finish_handoff`;
- тест: любой finish phase оставляет transaction journal и может быть resumed/rolled back;
- тест: board scan не видит `plan/roadmap-*.queue.yaml` и `plan-*.md` как runtime source;
- тест: checkpoint path совпадает с config-derived state dir;
- полный `bin/pytest -q` после очистки текущих dirty changes.

## Верификация аудита

Запущено из корня репозитория:

- после последовательной очистки целевые группы прошли: finish **67 passed**, import/resolver/episodes **96 passed**, board/v2 **107 passed**, identity/session-start **117 passed**, index/parallel/integrity **36 passed**, episode/runner **35 passed**;
- итоговые regression-матрицы после последней правки: core loop/finish/session **327 passed**, resolver/runner/board/index/parallel **329 passed**;
- compatibility shim `loop/loop.sh` дополнительно проверен: **6 passed**;
- полный `bin/pytest -q --tb=line` ранее не завершился в встроенном лимите `bin/pytest` 300 секунд; это не объявляется полным PASS;
- коммитов не выполнялось; рабочее дерево содержит изменения текущего эпика и результаты этой очистки.

## Статус последовательной очистки 2026-09-18

Выполнено:

- P0-01: live `REFLECT` удалён из phase/finish/runtime command paths; архивный `reflection_done` сохранён только для replay.
- P0-02: основной runtime index resolver и finish/read paths переведены на YAML v2; MD-only index не является lifecycle source.
- P1-03/P1-04/P1-05: pack fallback закрыт, incomplete SessionStart стал machine halt, public `finish_handoff` удалён.
- P1-06: `finish_decompose/plan/audit/creative` переведены на общий `commit_finish_context`; transaction regression guard добавлен.
- P1-07: runner, bundle resolver, episodes, roadmap и board imports используют canonical package owners; resolution fallback больше не проглатывается.
- P1-08: checkpoint identity добавлена в единый `resolve_session_identity`; mismatch даёт typed drift и machine halt.
- P2-09/P2-10/P2-11/P2-12: board legacy globs удалены, index writers используют общий atomic owner, checkpoint path стал config-derived, episode bundle пишет typed partial errors и не читает старый snapshot source.

Оставлено сознательно:

- `loop/loop.sh` остаётся тонким compatibility shim: repository-wide scan нашёл живые вызовы в `make`, e2e/smoke tests и active instructions. Это не второй исполнительный loop; удаление сейчас нарушило бы существующие consumers.
- YAML → MD human mirror и offline v1→v2 migration остаются, но не должны участвовать в lifecycle decision path.

Остаточная зона для следующего отдельного прохода: полная унификация уже transaction-based `finish_implement/qa/bugfix` с новым helper без изменения их event-ordering, а также чистка более широкого исторического bare-import корпуса в hook-модулях. Эти пути не удалялись вслепую, потому что вокруг них есть legacy fixture/adaptor consumers.

## Финальное решение

Не нужно оставлять все найденные варианты «на всякий случай». Правильная модель loop уже определена: **один resolver, один lifecycle reducer, один transaction finish, один runtime spawn path, один YAML decision source**. Всё, что остаётся только для совместимости, должно быть изолировано в offline migration и иметь срок удаления. Всё, что участвует в live decision одновременно с canonical path, является кандидатом на удаление по списку выше.
