---
schema: epic-reflect/v1
epic_id: T-HUB-016-dsh-cc-hooks-bridge
task_id: T-HUB-016
date: "2026-08-30"
author: gpt
verdict: PASS
---

# Ретроспектива эпика T-HUB-016-dsh-cc-hooks-bridge

## Итог

Эпик подключил официальный Claude Code hooks bridge к `epic-*` DSH-профилям и сохранил существующие Python hooks как источник поведения. Реализованы shared Cordis fragment, pinned package wiring, idempotent installer, передачa `DSH_HOOKS_BRIDGE` и `CLAUDE_PROJECT_DIR`, DSH self-limit в `stop-gate`, optional `dsh-claude-compat` mount, smoke/regression coverage и документация с указателем на T-HUB-008.

Аудит после первичных s01–s07 выявил пять отклонений. Append-only remediation s08–s12 добавила live dump-config evidence, исполняемый Claude-path regression, compat fixture/fail-soft smoke, configurable self-limit с default/override/invalid checks и required-config diagnostic smoke. Повторный BACK QA завершён с `verdict: pass`, пустыми `issues`, `blockers` и `fix_plan`; reviewer gate дал `VERDICT: PASS`.

Дополнительный BUGFIX закрыл adapter wiring: entrypoint теперь подключает `task-board.stock-run` и `workspace.list`, а `epic-bugfix` получил синхронизированный lockfile. Все 12 шагов канонического `index.yaml` имеют статус `completed`. REFLECT не изменяла code surfaces: `code_changed: no`.

Границы сохранены: существующая логика `stop-gate` и `agent-pretool` не переписана в TypeScript; non-mb stock-run продолжает делегироваться исходному handler; optional compat остаётся fail-soft; required bridge config завершается диагностируемо без silent fallback; board/loop и product memory-bank не смешиваются.

## vs plan / decompose

| Требование / outcome | Покрытие | Статус |
|---|---|---|
| Gap matrix и version pin для bridge | s01 | ✅ |
| Shared `cc-hooks-bridge` fragment подключён ко всем `epic-*` profiles | s02, s03, s07 | ✅ |
| `configPath` и `projectDir` получают значения из `CLAUDE_PROJECT_DIR` | s02, s04, s07 | ✅ |
| `DSH_HOOKS_BRIDGE` и loop environment проходят через `loop.sh` | s04, s07 | ✅ |
| DSH self-limit предотвращает бесконечный block→continue цикл | s05, s11 | ✅ |
| Self-limit имеет validated default, valid override и fail-closed invalid override | s11 | ✅ |
| `dsh-claude-compat` доступен как optional mount и не блокирует boot | s06, s10 | ✅ |
| Required bridge config даёт loud diagnostic и не выбирает free-session fallback | s02, s12 | ✅ |
| Smoke/regression documentation и config evidence | s07–s10 | ✅ |
| Live `task-board.stock-run` adapter registration | BUGFIX B1, QA integration check | ✅ |
| Live `workspace.list` adapter registration | BUGFIX B2, QA integration check | ✅ |
| Profile dependency и lockfile синхронизированы | BUGFIX B3, targeted tests | ✅ |
| AC+/AC−, §0.11 producer/consumer paths и fail-closed boundaries | BACK QA + reviewer | ✅ |

Первичный аудит имел 5 findings; все findings закрыты s08–s12 либо последующим точечным BUGFIX. Незакрытых `legacy_surfaces_remaining`, `fallback_remaining` и blockers нет.

## Successes

- Bridge wiring остался аддитивным: DSH вызывает существующие hooks вместо дублирования Python-логики в TypeScript.
- Профили используют pinned dependency и общий fragment, поэтому конфигурация не расходится между `epic-audit`, `epic-bugfix`, `epic-creative`, `epic-decompose`, `epic-implement`, `epic-plan`, `epic-qa` и `epic-reflect`.
- Required и optional пути явно разделены: ошибка обязательного `configPath` наблюдаема, а отсутствие compat package не превращается в boot failure.
- Remediation была атомарной и трассируемой: каждый audit finding получил собственный s08–s12 shard и evidence.
- После QA failure исправлен именно runtime adapter contract, а не ослаблены тесты или stop-gate.
- Проверены malformed config, missing package, invalid self-limit, step mismatch, disabled bridge, non-mb delegation и отсутствие fallback.
- Полный backend suite завершился без failures; `compileall`, shell syntax и `git diff --check` также прошли.

## Problems

- Первичная реализация дошла до QA с отсутствующими live adapter registrations для `task-board.stock-run` и `workspace.list`; статические fragment checks не гарантировали entrypoint wiring.
- Первый audit не имел live dump-config, исполняемой Claude-path regression, compat fixture и required-config failure evidence. Эти проверки пришлось добавлять отдельными remediation steps.
- В `events.jsonl` зафиксированы `audit_done`, два `qa_fail` и два `bugfix_done`, но отсутствует machine-readable `qa_pass` и отсутствуют `implement_done` события. Timeline восстанавливается из артефактов, но не самодостаточен.
- Runtime snapshots не согласованы с завершённым QA: `last-session.json` содержит transient abort на BUGFIX и `retry_count: 1`, `state.json` — `state_rebuilt: true`, `status: running`, `fingerprint_stall_count: 1`, тогда как текущий рабочий этап уже REFLECT.
- Dirty snapshot содержит поверхности других эпиков и baseline не зафиксирован; поэтому нельзя автоматически отличить чужую незакоммиченную работу от изменений текущего эпика.
- Рабочая сессия ранее завершилась fingerprint stall без обновления `activeContext.md`; outer retry потребовал заново записать единственный Handoff перед продолжением REFLECT.
- Frontend runners не запускались: scope — BACK tooling/repository validation, а TypeScript package не предоставляет применимого frontend test script. Это ограничение scope, не дефект AC.

## Lessons

1. Static YAML/package presence не доказывает Cordis runtime wiring. Для каждого producer/consumer slot нужен live или executable adapter assertion.
2. Каждая обязательная конфигурация должна иметь проверяемый error channel; `required: true` без failure smoke оставляет silent fallback недоказанным.
3. Audit remediation лучше оформлять отдельными append-only shards: так видно, какое evidence закрыло конкретный finding, и не теряется история.
4. QA должен проверять интеграционные seams до полного suite: entrypoint adapters, environment propagation, package/lockfile и error channels дают более сильный сигнал, чем isolated source checks.
5. Runtime retry, resume, state rebuild и progress advance — разные события. Один `retry_count` и общий `status` требуют ручной интерпретации и создают риск fingerprint stall.
6. Handoff является частью надёжности оркестрации: stale `activeContext.md` способен остановить уже успешно завершённый переход, даже когда code и QA evidence зелёные.

## Improvements

- Добавить pre-QA integration checklist для live registration, Host RPC adapters, result propagation, environment propagation и required/optional error channels.
- Эмитировать `implement_done`, `qa_fail` с reason/fix target, `bugfix_done` с advance marker и `qa_pass` с covered scope в machine-readable event log.
- Разделить counters на `qa_fail`, `bugfix_advance`, `retry_without_advance`, `external_abort`, `state_rebuild`, `resume_dirty` и `fingerprint_stall`.
- Сохранять fingerprint и baseline dirty paths перед началом эпика; при смешанном workspace показывать scoped diff вместо общего dirty snapshot.
- Добавить consistency check между YAML SoT, human-readable `index.md` и event log, включая проверку финальных статусов и обязательного `qa_pass`.
- На FINISH проверять, что `activeContext.md` обновлён после последнего зелёного gate и содержит ровно один Handoff, прежде чем runner может продолжить.

## Orchestration signals

| Источник | Сигнал | Интерпретация |
|---|---|---|
| `events.jsonl` seq1–5 | `audit_done`, 2× `qa_fail`, 2× `bugfix_done`; `qa_pass` отсутствует | Конечные remediation cycles с advance были, но completion event неполон. |
| `last-session.json` | `status: aborted`, `abort_kind: transient`, `retryable: true`, `retry_count: 1`, `resume_dirty: true`, resume `BUGFIX` | Снимок предыдущего transient abort, не product failure; нуждается в отделении retry от advance. |
| `checkpoint.json` | checkpoint подготовлен для `BACK/BUGFIX`, `status: active` | Устаревший checkpoint не отражает текущий REFLECT transition. |
| `state.json` | `state_rebuilt: true`, `diagnostic_codes: [state_rebuilt]`, `fingerprint_stall_count: 1`, `status: running` | Projection была восстановлена, а fingerprint stall подтвердился; state не синхронизирован с текущим Handoff. |
| runtime dirty snapshot | Пути T-HUB-016 смешаны с планами/артефактами других эпиков | Чужая dirty work наблюдается, но без baseline нельзя установить происхождение; текущая REFLECT code-free. |
| текущий Handoff | Предыдущая сессия не записала смену QA→REFLECT | Реальный session-abort/stall; исправлено полной записью `activeContext.md` перед работой. |
| session logs | Ожидаемый `runtime/dev-hub/epic/session-2.log` в checkout не найден | Аномалию нельзя детализировать по полному log dump; использованы bounded runtime snapshots и event log. |

## Promote candidates

| Сигнал | Решение | Кандидат |
|---|---|---|
| Отсутствующий `qa_pass` и неполный implement timeline | `→ loop/hooks` | Добавить обязательную emission и валидацию lifecycle events при переходах QA/IMPLEMENT. |
| `state_rebuilt`, transient abort и смешанный `retry_count` | `→ loop/hooks` | Развести diagnostic counters и не оставлять `status: running` после восстановленного abort без нового action. |
| Fingerprint stall из-за stale Handoff | `→ loop/hooks` | Добавить FINISH shape/fingerprint gate: последний зелёный gate должен сопровождаться актуальным единственным Handoff. |
| Live adapters не были видны статическими checks | `→ workflow` | Встроить pre-QA producer/consumer checklist и executable slot smoke в BACK QA. |
| Dirty paths других эпиков без baseline | `→ workflow` | Добавить preflight dirty baseline и scoped ownership report до IMPLEMENT/QA. |
| Два QA failure с последующим advance | `→ workflow` | Сохранять reason/fix target в `qa_fail` и `bugfix_done`, чтобы remediation была машинно объяснима. |
| Graphify отсутствует в hub/tooling checkout | `→ skip` | Применён разрешённый inventory fallback; текущий tooling epic не блокируется. |
| Frontend test runners неприменимы для BACK scope | `→ skip` | Не создавать искусственный frontend QA scope; backend suite и source-contract checks достаточны. |
| ARCHIVE NOW в текущем REFLECT чате | `→ skip` | Архивацию выполнять отдельной командой и новым чатом после остановки runner. |

## Метрики

- Шагов: 12 / 12 completed (100%).
- Первичный audit: 5 findings; remediation s08–s12 закрыла все findings.
- BUGFIX: B1/B2/B3 закрыты; adapter wiring подтверждён targeted regression.
- Targeted BUGFIX regression: 24 passed.
- Full repository suite: 7863 passed, 181 skipped, 48 warnings.
- `compileall`: pass; shell syntax: pass; `git diff --check`: pass.
- Final BACK QA: `verdict: pass`, issues 0, blockers 0, fix_plan 0; reviewer `VERDICT: PASS`.
- Orchestration: 5 event records observed; 2 QA failures, 2 bugfix advances; completion event missing.
- Runtime: transient abort snapshot, `retry_count: 1`, `resume_dirty: true`, `state_rebuilt: true`, `fingerprint_stall_count: 1` — recorded as orchestration signals, not AC failures.
- Frontend tests: не применялись к BACK tooling scope.
- Graphify: N/A для hub checkout; inventory fallback разрешён правилами.
- `code_changed` этой REFLECT-сессии: no.

## Next

BACK REFLECT завершён с PASS. Следующий шаг — `BACK ARCHIVE NOW` в новом чате после остановки runner; ARCHIVE NOW не запускать внутри текущей REFLECT-сессии. Если улучшения из Promote candidates будут реализовываться, их следует вести отдельным workflow/эпиком, не смешивая с архивацией T-HUB-016.
