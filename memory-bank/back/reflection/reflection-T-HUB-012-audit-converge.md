---
schema: epic-reflect/v1
epic_id: T-HUB-012-audit-converge
task_id: T-HUB-012
date: "2026-08-28"
author: gpt
verdict: PASS
---

# Ретроспектива эпика T-HUB-012-audit-converge

## Итог

Эпик усилил BACK/FRONT/INTEG AUDIT семантикой Spec Kit converge без введения нового режима: audit template переведён на additive `epic-audit/v2`, добавлены `findings[]`, `intent_checked` и `converged`, а legacy-массивы сохранены для dual-write и чтения старых артефактов. Во всех трёх ролях зафиксирован единый bounded pipeline Intent Inventory → Assess → Severity → Append → Converged/QA с `gap_type`, `severity`, `source_ref`, evidence и leftover gates.

Завершены все четыре шага decompose index: s01 — template/README mapping, s02 — BACK workflow и lean gates, s03 — FRONT/INTEG parity, s04 — finish routing, refs, fixture и purge устаревших doc claims. Финальный fixture показывает, что FR без реализации становится `missing` finding с `HIGH`/`CRITICAL`, `source_ref` и путём нового audit shard; `unrequested` остаётся finding-only и не вызывает автоудаление.

Первый QA выявил внешний cross-cutting blocker полного backend suite (`110 failed, 7565 passed, 181 skipped`), не дефект audit-converge AC. После BUGFIX-цикла, документированного в `bugfix-20260827-global-suite-regressions.md`, повторный QA прошёл: `7678 passed, 181 skipped, 48 warnings`; `issues`, `blockers` и `fix_plan` пусты. Эта REFLECT-сессия не меняла product/code surfaces: `code_changed: no`.

## vs plan / decompose

| Требование | Покрытие | Статус |
|---|---|---|
| FR-1: `epic-audit/v2`, `findings[]`, `intent_checked`, `converged` | s01; финальный QA AC+ #1 | ✅ |
| FR-2: additive dual-write legacy `implemented` / `not_implemented` / `deviations` / leftovers | s01; QA AC− #3 и AC+ #1 | ✅ |
| FR-3: общий Intent Inventory → Assess → Severity → Append → Converged/QA для BACK/FRONT/INTEG | s02–s03; QA AC+ #2/#3 | ✅ |
| FR-4: `source_ref` в goal/plan_refs каждого нового audit shard | s01, s02, s04; QA §0.11 и AC+ #2/#4 | ✅ |
| FR-5: CRITICAL constitution/P1 missing в начале findings/not_implemented | s01–s02; fixture и QA AC+ #4 | ✅ |
| FR-6: `converged: true` и пустые actionable/leftover → QA, иначе новый IMPLEMENT → AUDIT | s02, s04; QA AC+ #5/#6 | ✅ |
| FR-7: явная граница ANALYZE (T-HUB-011) и AUDIT (T-HUB-012) | s02, s03, s04; QA AC− #4 | ✅ |
| FR-8: refs `speckit-adapt-012.md` | s04; QA static checks | ✅ |
| FR-9: пример/fixture finding row | s01, s04; `expected-audit-findings.yaml` | ✅ |
| FR-10: `finish-doc-router` учитывает `converged` | s04; QA AC+ #6 | ✅ |
| NFR-1: completed implement artifacts append-only | s02–s03; QA AC− | ✅ |
| NFR-2: без git history diff / branch compare | s02–s03; QA AC− | ✅ |
| NFR-3: bounded/token-lean inventory из plan и shard paths | s01–s03; QA §0.11 | ✅ |
| NFR-4: legacy A/B/C leftover gates не ослаблены | s01–s03; финальный leftover gate | ✅ |
| NFR-5: не трогать specify-cli, MODE CONVERGE и ANALYZE contract | s02–s04; QA AC− | ✅ |
| Replacement cleanup: exclusive step-only claims и старый QA routing | s02–s04; `legacy_surfaces_remaining=[]`, `fallback_remaining=[]`, `purge_step_present=true` | ✅ |

Decompose index подтверждает `s01`–`s04: completed`, `not_implemented: []`, `deviations: []`, `converged: true` и исчерпанную очередь. Реализация сохранила заявленный scope: docs/templates/rules/fixture; executable audit engine и отдельный `CONVERGE` command не добавлялись.

## Successes

- Additive v2-контракт расширяет audit evidence, не ломая v1-поля и старые YAML.
- BACK, FRONT и INTEG получили parity по смыслу, при этом сохранены role-specific paths и `step_id`/`element_id` identity.
- Converged routing стал проверяемым: одного пустого `not_implemented[]` недостаточно, нужны `converged: true` и пустые actionable/leftover arrays.
- `source_ref` проведён от intent finding до remediation shard, что сохраняет трассируемость FR/SC/US/AC/constitution.
- `unrequested` явно ограничен finding-only policy; автоматическое удаление кода не появилось.
- Dry-run fixture покрывает существенный failure mode — FR существует, но реализации нет — без подключения runtime engine.
- Финальный doc-claim purge устранил старое утверждение, что AUDIT проверяет только presence `step_id`.
- Первый suite blocker не был замаскирован: QA сохранил исторический FAIL как evidence, а повторный QA отдельно подтвердил свежий PASS.
- Полный parent backend suite и статические `py_compile`/`bash -n` проверки завершились успешно; frontend runner неприменим к текущему backend docs/template scope.

## Problems

1. Первый QA 2026-08-24 был красным из-за cross-cutting runtime lifecycle regression: contamination `PROJECT_ROOT`/`DEV_HUB`, checkpoint resume mismatch и stale DSH arm scope. Причина была вне audit-converge surfaces, но docs-эпик всё равно зависел от обязательного глобального suite gate.
2. Event timeline неполон для реализации: в `events.jsonl` есть `audit_done`, два `qa_fail`, `bugfix_done` и `qa_pass`, но нет `implement_done` для s01–s04. Фактическая реализация подтверждается decompose/implement artifacts и delivery log, однако оркестрация не отражает полный путь.
3. Runtime snapshots дают смешанные сигналы. `last-session.json` отмечает `completed`/`clean`, `retry_count: 1`, `resume_dirty: false`, но содержит `state_rebuilt` и stale `last_verify_evidence` от T-HUB-007; `state.json` в момент REFLECT остаётся `active/running`, а checkpoint имеет `stage: prepared`. Это telemetry/state synchronization issue, не product defect текущего эпика.
4. Dirty snapshot чрезмерно широк: около 210995 записей, включая 208802 под `dsh`, 1958 под `graphify-out`, 124 под `memory-bank` и только 22 упоминания T-HUB-012. Такой снимок плохо отделяет owning epic от чужих или generated surfaces.
5. Доступный `runtime/dev-hub/epic/session-1.log` велик и смешан с transcript/tool output; targeted scan находит общие маркеры `abort`/`halt`/`retry`, но не даёт надёжного current-epic abort-сигнала. Полный dump в reflection не переносился намеренно.
6. `graphify update` для REFLECT не запускался по канону (`code_changed: no`), поэтому graph evidence для этого шага не требуется. Ограничение зафиксировано, а не скрыто.

## Lessons

1. AUDIT converge должен быть additive к существующей step matrix: intent findings расширяют presence evidence, а не заменяют её.
2. `source_ref` — обязательный переносимый идентификатор, а не только поле верхнего audit YAML; без него новый remediation shard теряет связь с исходным FR/AC.
3. `converged` следует трактовать как составной lifecycle gate вместе с пустыми actionable и legacy leftover массивами.
4. Для docs/tooling-эпика нужен bounded static fixture: он проверяет failure semantics дешевле и точнее, чем искусственный runtime engine или полный frontend suite.
5. Cross-cutting runtime regressions могут блокировать QA эпика, даже если собственные AC surfaces проходят. Поэтому исторический FAIL, remediation и свежий PASS должны оставаться отдельными evidence artifacts.
6. Event log, runtime snapshot, checkpoint и working-tree snapshot — разные источники истины. Их нельзя молча сливать в один статус: stale cross-epic evidence нужно маркировать явно.
7. Отсутствие `implement_done` снижает наблюдаемость, но не отменяет проверяемость при наличии completed shards, QA pass и delivery log; emission всё равно является качеством оркестрации.

## Improvements

- На `finalize-step` добавить `implement_done` для каждого sNN либо одно batch-событие с полным списком шагов и artifact hashes.
- При arm нового эпика очищать или scope-валидировать `last_verify_evidence`, чтобы PASS от T-HUB-007 не отображался внутри T-HUB-012.
- В runtime snapshots разделить `owning_epic_dirty`, `foreign_epic_dirty` и generated/tooling dirty; не считать весь DSH/graphify объём одним blocker.
- В hooks/fixtures сохранять эффективные `PROJECT_ROOT`/`DEV_HUB` и короткий diagnostic summary, а не только stale session path или полный transcript.
- Для обязательного suite перед повторным QA использовать deterministic clean-env preflight и компактную агрегацию причин `qa_fail → bugfix_done → qa_pass`.
- При state rebuild synchronously обновлять `state.json`, `checkpoint.json` и `last-session.json`, чтобы `active/running`, `prepared` и `completed/clean` не расходились после одного lifecycle transition.
- Сохранить source-scoped QA для docs-only AUDIT, но явно показывать в QA artifact, когда глобальный backend suite применён как cross-cutting regression gate.

## Orchestration signals

| Источник | Наблюдение | Интерпретация |
|---|---|---|
| `memory-bank/back/events/T-HUB-012-audit-converge/events.jsonl` | seq1 `audit_done`; seq2 и seq3 `qa_fail`; seq4 `bugfix_done`; seq5 `qa_pass` | Был реальный QA-fail → remediation → PASS advance; бесконечного retry-loop не обнаружено |
| QA repeat artifact | `verdict: pass`, `issues: []`, `blockers: []`, `fix_plan: []` | Текущий эпик допускает REFLECT |
| Decompose index | 4/4 steps `completed`; queue исчерпана | Нет pending implement shard; lifecycle scope завершён |
| Audit artifact | `converged: true`, `not_implemented: []`, `legacy_surfaces_remaining: []`, `fallback_remaining: []` | AUDIT convergence достигнут до QA |
| `.claude/runtime/epic/checkpoint.json` | current identity `BACK/REFLECT`, `stage: prepared`, `status: active`, `retry_count: 0` | Текущий REFLECT invocation подготовлен; не признак product failure |
| `.claude/runtime/epic/last-session.json` | `status: completed`, `outcome: clean`, `retry_count: 1`, `resume_dirty: false`, `step_id: REFLECT`, `state_rebuilt: true` | Последний snapshot завершён чисто, но содержит rebuild telemetry |
| `.claude/runtime/epic/last-session.json` | `last_verify_evidence.epic_id: T-HUB-007-dsh-profiles-presets` при armed epic T-HUB-012 | Stale cross-epic verify evidence; нужен scope reset, не переоткрытие T-HUB-012 |
| `.claude/runtime/epic/state.json` | `active: true`, `status: running`, phase `REFLECT`, diagnostic `state_rebuilt` | Runner ещё удерживает текущую REFLECT lifecycle state до stop |
| dirty snapshot | ~210995 entries, доминируют `dsh` и `graphify-out`; 22 T-HUB-012 matches | Snapshot не scoped к эпику; сигнал загрязнён чужими/generated surfaces |
| `runtime/dev-hub/epic/session-1.log` | большой смешанный transcript; targeted markers без подтверждённого current-epic abort/halt | Наблюдаемость ограничена; полный log в artifact не переносился |
| роль/фаза | `BACK IMPLEMENT` → `BACK AUDIT` → `BACK QA` → `BACK BUGFIX` → `BACK QA repeat` → `BACK REFLECT` | Role ownership и phase progression согласованы; skip QA не обнаружен |

**Вывод layer B:** бизнес-путь эпика дошёл до PASS и REFLECT с реальным remediation advance. Основные аномалии относятся к неполному event emission, stale cross-epic verify snapshot, широкому dirty snapshot и слабой диагностике session log; они не требуют переоткрывать закрытые AC.

## Promote candidates

| Сигнал | Решение |
|---|---|
| Нет `implement_done` в event log | → loop/hooks: emission на `finalize-step` или batch-событие |
| Два `qa_fail` до `qa_pass` без компактных progress markers | → loop/hooks: агрегировать причины и advance markers QA/BUGFIX |
| Stale `last_verify_evidence` от другого epic | → loop/hooks: scope reset при arm/resume и reject cross-epic evidence |
| `state_rebuilt` при разных status snapshot | → workflow: добавить synchronized state transition summary; не менять текущий epic retrospectively |
| Dirty snapshot с огромными foreign/generated деревьями | → loop/hooks: scoped dirty classification; не считать его blocker без owning-path match |
| Смешанный session log и отсутствие короткого diagnostic summary | → workflow: retention/summary для abort/halt/FINISH; не читать полный dump в REFLECT |
| Первый глобальный suite FAIL устранён и свежий suite PASS | → workflow: сохранить clean-env preflight и повторный QA gate |
| Frontend runner отсутствует в backend docs/template scope | → skip: frontend tests не применяются |
| `graphify update` при `code_changed: no` | → skip: REFLECT не менял code surfaces |
| `MODE CONVERGE`, auto-delete `unrequested`, rewrite completed shards | → skip: запрещённые поверхности не вводились |
| Нет executable audit engine в scope | → skip: отдельная будущая задача, не gap текущего эпика |
| Greenfield/docs-process replacement B/C | → skip: `n/a`, legacy fallback cleanup закрыт в текущем audit |

## Метрики

- Шагов: 4 / 4 completed (100%).
- Audit: `converged: true`; actionable findings и leftover-массивы пусты.
- QA: финальный `verdict: pass`; issues 0; blockers 0; fix_plan 0.
- Event log: 5 событий — 1 `audit_done`, 2 `qa_fail`, 1 `bugfix_done`, 1 `qa_pass`.
- Parent suite: 7678 passed, 181 skipped, 48 warnings.
- Static checks: `py_compile` и `bash -n loop/loop.sh` — PASS.
- Frontend tests: неприменимы; frontend surfaces в scope отсутствуют.
- Graphify: не запускался, поскольку `code_changed: no`.
- Orchestration: `last-session.retry_count: 1`, `resume_dirty: false`, `state_rebuilt: true`; stale cross-epic verify evidence отмечен.
- Эта REFLECT-сессия: `code_changed: no`.

## Next

Эпик завершён с PASS; после handoff фиксируется отдельная строка `EPIC_DONE`. Архивация артефактов отложена до остановки текущего runner и выполняется вручную вне этой REFLECT-сессии. Promote-кандидаты выше — отдельные улучшения оркестрации, не незакрытые требования T-HUB-012.
