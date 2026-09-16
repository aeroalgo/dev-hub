# [T-HUB-106 | dsh-runtime-full-purge] PLAN

**Дата:** 2026-09-16  
**Режим:** BACK PLAN  
**Уровень:** L3  
**Статус:** active  
**Clarify:** [clarify-20260916-dsh-full-purge.md](../../clarify/clarify-20260916-dsh-full-purge.md)  
**Prompt:** [md/prompt.md](prompt.md) — outcome SoT (абстрактный; не HOW)  
**Roadmap:** `memory-bank/back/roadmap/queue.yaml` · batch `dsh-runtime-full-purge-20260916` · `kind: feature`  
**Deps:** —  
**Skills:** writing-plans · python-testing-patterns · architecture-patterns · grill-me (Phase 0)  
**Источник:** chat BACK PLAN «выпилить DSH полностью» + clarify override

---

## Контекст

- **req:** Убрать из dev-hub **всю live-реализацию DSH**: дерево `dsh/` (profiles/presets/plugins/patches/scripts/bin), Python runtime adapter, registry/CLI/env wiring, harness DSH-bridge/filters, obsolete tests, live operator/instruction surfaces, которые учат DSH как поддерживаемый runtime.
- **status quo:** `loop/runtime_registry.yaml` регистрирует `dsh` → `loop.runtime_adapters.dsh.DshAdapter`; `bin/loop dsh` / `EPIC_RUNTIME=dsh` / `runtime_sync --runtime dsh|all`; phase registry несёт `dsh_preset`; docs (`DSH.md`, runbooks, `LOOP-RUNTIMES.md`, architecture) описывают pilot.
- **gap:** третий runtime + Cordis/TS libs увеличивают поверхность поддержки; после Python supervisor cutover DSH остаётся first-class без продуктовой необходимости.
- **refs (sunset seed):** `dsh/**` · `loop/runtime_adapters/dsh.py` · `loop/runtime_registry.yaml` · `loop/cli/runtime_sync.py` · `loop/runner/config.py` · `loop/prompt_builder.py` · `loop/epic_transition.py` (`get_dsh_preset`) · `harness/hooks/dsh_stream_filter.py` · `harness/hooks/session_resilience.py` · `harness/manifest.yaml` · `bin/loop` · `loop/tests/test_loop_dsh_dispatch.py` · `loop/tests/test_dsh_e2e_smoke.py` · mixed tests с `runtime="dsh"`.
- **Не в scope:** rewrite/delete historical `memory-bank/**/plan|qa|audit|events` деревьев DSH-эпиков (006–020 и др.); Claude/Codex adapters как таковые; Cursor IDE runtime.

**CREATIVE need:** нет.

---

## Delivery closure

| Capability / outcome | Classification | Production entrypoint and caller | Success / failure enforcement | Independent outcome test | Foundation approval / follow-up |
|---|---|---|---|---|---|
| Sole agent runtimes без DSH | `vertical_slice` | `bin/loop` / `context_loop.prepare_session` / `get_adapter_for_runtime` / `runtime_registry` | `dsh` / aliases → ValueError / CLI exit ≠0; registry без ключа `dsh`; нет import `DshAdapter` | Given registry+CLI без dsh; When `EPIC_RUNTIME=dsh` или `--runtime dsh`; Then fail-closed, не claude fallback | `n/a` |
| Удаление tree `dsh/` + install scripts | `vertical_slice` | repo layout + adapter prep hooks | path `dsh/` отсутствует; install scripts не вызываются | Given checkout после эпика; When `test -d dsh`; Then fail | `n/a` |
| Kind I: агент/оператор не учит DSH как live SoT | `vertical_slice` | `AGENTS.md` / `CLAUDE.md` / `harness/instructions/main.md` / README / LOOP-RUNTIMES / runbooks | нет ветки «DSH → AGENTS.md» как supported runtime; `DSH.md` удалён или не учит live path | Given instruction surfaces; When rg live teaching patterns; Then 0 hits | `n/a` |

---

## Technology axiom (replace-not-wrap)

| Выбор | Machine input | FORBIDDEN после эпика |
|-------|---------------|------------------------|
| Runtime SoT | `loop/runtime_registry.yaml` keys ∈ {`claude`, `codex`} (+ aliases только `claude-code`→`claude`) | ключ/адаптер `dsh`; alias `deepseek-harness`/`deepseek`→`dsh` |
| Session prepare | явный runtime id из env/CLI, validate-against-registry | silent map `dsh`→`claude`; `DSH_HOOKS_BRIDGE=1` ветка |
| Phase config | phase registry **без** machine field `dsh_preset` (или поле удалено/игнорируется с fail если передано) | `get_dsh_preset` / `arm_epic(..., dsh_preset=)` как live API |
| Entrypoint | `bin/loop` accepts `claude\|codex` only | `case …\|dsh)` |

As-built = **sunset inventory only**, не шаблон «оставить shim на потом».

---

## Продуктовая спека (WHAT)

Оператор и loop используют только поддерживаемые agent runtimes. DSH больше не является опцией запуска, установки профилей или документированным live path. Попытка выбрать DSH даёт понятную ошибку. Код, библиотеки под `dsh/` и тесты, закрепляющие DSH-контракт, отсутствуют.

### Product probe

| # | Question | Answer / Probe | Decision / Impact on PLAN |
|---|----------|----------------|---------------------------|
| 1 | **Reframe** | Убрать третий runtime и его libs, а не «почистить docs» | Full live purge + Kind I |
| 2 | **Narrowest wedge** | Registry deny + delete adapter + delete tree + rewrite tests | Ladder wire→enforce→purge |
| 3 | **Pre-mortem** | Оставить silent fallback dsh→claude «чтобы CI green» | AC− forbid; rewrite tests first |
| 4 | **Distribution** | README / LOOP-RUNTIMES / AGENTS·CLAUDE без DSH | Kind I в том же эпике |
| 5 | **Technical leverage** | Удалить Cordis profiles/plugins целиком | `deletes: dsh/` |
| 6 | **Appetite** | ~2–3 дня; history epics не трогать | cut_list = history scrub |

### User Stories

| # | Story | Priority | Independent Test |
| :--- | :--- | :--- | :--- |
| US-001 | Как оператор loop, я хочу, чтобы поддерживались только Claude Code и Codex, чтобы не поддерживать DSH. | P0 | `prepare_session` / CLI с `dsh` → ошибка; registry без `dsh` |
| US-002 | Как разработчик hub, я хочу отсутствие дерева `dsh/` и DSH-адаптера, чтобы не тянуть Cordis/plugins. | P0 | `test -d dsh` fail; import `loop.runtime_adapters.dsh` fail |
| US-003 | Как агент по AGENTS/CLAUDE, я не должен получать инструкцию выбирать DSH runtime. | P0 | rg Kind I teaching patterns = 0 |

#### Acceptance Scenarios — US-001

- **Given:** checkout после эпика, registry без `dsh`
- **When:** `EPIC_RUNTIME=dsh` или `bin/loop dsh …` или `--runtime dsh`
- **Then:** non-zero / raise с явной ошибкой unknown/unsupported runtime; процесс **не** стартует как claude

#### Acceptance Scenarios — US-002

- **Given:** repo root после эпика
- **When:** проверка наличия `dsh/` и модуля `loop.runtime_adapters.dsh`
- **Then:** директории/модуля нет; targeted suite green без DSH fixtures

#### Acceptance Scenarios — US-003

- **Given:** `AGENTS.md`, `CLAUDE.md`, `harness/instructions/main.md`, README runtime table
- **When:** поиск live «DSH → …» / `EPIC_RUNTIME=dsh` as supported
- **Then:** 0 hits (исторические epic trees memory-bank вне scope)

### Functional Requirements (FR-###)

- **FR-001:** Система должна отвергать runtime id `dsh` (и бывшие aliases на dsh) на CLI, env и factory adapter с fail-closed ошибкой.
- **FR-002:** Система должна иметь registry SoT только для `claude` и `codex` (плюс documented alias `claude-code`).
- **FR-003:** Система должна удалить пакет/дерево `dsh/` включая scripts install-profiles / install-cc-hooks / which-dsh.
- **FR-004:** Система должна удалить `DshAdapter` и все prod call sites / imports.
- **FR-005:** Система должна убрать machine field/API `dsh_preset` / `get_dsh_preset` из live phase arm path (delete symbol или fail если передано — без no-op keep).
- **FR-006:** Система должна удалить harness DSH-only surfaces: `dsh_stream_filter.py`, DSH abort/mismatch branches, manifest dsh blocks, `DSH_HOOKS_BRIDGE` wiring.
- **FR-007:** Система должна удалить или переписать тесты, которые требуют DSH-контракт (включая `test_loop_dsh_dispatch.py`, `test_dsh_e2e_smoke.py` и кейсы `runtime="dsh"`).
- **FR-008:** Система должна переписать live Kind I (AGENTS/CLAUDE/instructions/README/LOOP-RUNTIMES/runbooks/architecture index) так, чтобы DSH не был supported runtime; удалить `DSH.md` и `docs/runbooks/dsh-loop-pilot.md` и `memory-bank/architecture/dsh-runtime.md` как live surfaces.
- **FR-009:** Misconfig / выбор dsh **не** должен молча деградировать в claude.

### Success Criteria (SC-###)

| ID | Измеримый результат | Проверка / источник | Type |
| :--- | :--- | :--- | :--- |
| SC-001 | `rg` prod: нет `DshAdapter` / `runtime_adapters.dsh` / registry key `dsh:` | `rg` + registry load | outcome |
| SC-002 | `test -d dsh` → false | shell | outcome |
| SC-003 | CLI/env `dsh` → fail | targeted pytest + CLI smoke | outcome |
| SC-004 | Kind I live teaching patterns = 0 | `rg` на allowlist paths | outcome |
| SC-005 | Targeted DSH-related suite deleted/rewritten; no restore-legacy to green | `bin/pytest` targeted | outcome |

### Assumptions

- Sole remaining runtimes после эпика: **claude** + **codex** (default остаётся текущий default без dsh).
- Historical memory-bank epic artifacts могут содержать слово «dsh» — **не** blocker QA для этого эпика (explicit out-of-scope).
- Внешний бинарь `dsh` на машине оператора может существовать; hub его не вызывает и не документирует.

### Clarifications

- Session: 2026-09-16 · [clarify-20260916-dsh-full-purge.md](../../clarify/clarify-20260916-dsh-full-purge.md)
- Q1 maximal scrub **superseded**: user — удалить код/рантайм/libs/тесты; эпики не трогать.
- Sole runtimes claude+codex — принято (status quo минус dsh).

### [НУЖНО УТОЧНИТЬ]

- нет открытых CRITICAL

## AC

1. Registry и factory не отдают DSH adapter; `dsh` → явная ошибка.
2. Дерево `dsh/` отсутствует в репо.
3. `bin/loop` / `runtime_sync` / prepare_session не принимают `dsh` как valid choice.
4. Prod-код без `DshAdapter`, `get_dsh_preset` live path, `DSH_HOOKS_BRIDGE` dsh-only wiring.
5. Obsolete DSH tests удалены; mixed tests переписаны на claude/codex или deny.
6. Live Kind I не учит DSH как supported runtime; `DSH.md` и dsh-runbook/architecture dsh-runtime удалены.
7. Targeted pytest green без восстановления DSH.

### AC− (brownfield replace)

1. Нет второго entrypoint на роль agent-runtime через DSH.
2. Нет soft default / silent `dsh`→`claude`.
3. Misconfig `EPIC_RUNTIME=dsh` → fail at start (non-zero / raise), не stub.
4. Нет prod dual-path registry с ключом `dsh` после эпика.
5. Нет живых тестов, требующих DSH-контракт.
6. Нет Kind I, требующих DSH как live SoT (на allowlist instruction paths).
7. Нет optional SoT «dsh available but deprecated» без follow-up ID.

---

## Техника / архитектура (HOW)

- **Стек:** Python loop + YAML registry; удаление TS/Cordis tree `dsh/` целиком (не миграция).
- **Стратегия:** characterization deny-tests → cutover registry/call sites → delete adapter module → delete `dsh/` → Kind I rewrite → consolidate tests → `*-legacy-fallback-purge` с полным `sunset_inventory` + `grep_control`.
- **Fail-closed:** `InvalidRuntimeConfig` / `ValueError("Unknown runtime: dsh")` / CLI argparse choices без dsh; запрещён `except: use claude`.
- **Phase registry:** удалить поле `dsh_preset` из schema/load path и symbol `get_dsh_preset`; callers (arm/epic_transition/harness epic core) очистить.
- **Board sync / host_url / workspaces:** любые path assumptions на `dsh/storages` в tests — переписать на нейтральные fixtures (не сохранять dsh layout).
- **Observability:** session_events dsh-specific normalize удалить; resilience DSH patterns удалить вместе с adapter.
- **History:** не трогать `memory-bank/back/plan/T-HUB-0*-dsh-*` и related qa/events.

## Eng review spine

### Data flow (ASCII)

```text
[Operator] --CLI/env--> [bin/loop | context_loop.prepare_session]
                              |
                              v
                    [runtime_registry.yaml] --validate--> {claude|codex} only
                              |
                    fail(dsh) | ok
                              v
                    [get_adapter_for_runtime] --> ClaudeAdapter | CodexAdapter
                              |
                              v
                    [session execute] --> no DSH_HOOKS_BRIDGE / no dsh profiles
```

### Failure matrix

| Component / link | Failure | Detection | User/system response | Test ID |
|------------------|---------|-----------|----------------------|---------|
| CLI `bin/loop dsh` | unsupported token | case/argparse | exit ≠0, usage | TM-001 |
| Env `EPIC_RUNTIME=dsh` | unknown runtime | prepare/validate | raise / non-zero | TM-002 |
| Registry missing dsh key | factory request dsh | InvalidRuntimeConfig | ValueError | TM-003 |
| Stale import `runtime_adapters.dsh` | ImportError | import / suite | fail closed (module gone) | TM-004 |
| Kind I leftover teaching | docs still say DSH supported | rg Kind I | FAIL purge | TM-005 |
| Test restores dsh fixture | obsolete assert | suite review | delete/rewrite test | TM-006 |
| Silent fallback to claude | dual path | code review + test | FORBIDDEN | TM-002 |

### Eng spine self-check

| Dimension | Score 1–5 | Gap / action |
|-----------|-----------|--------------|
| Data flow complete | 5 | — |
| Failure coverage | 5 | deny + no-fallback rows |
| Testability | 5 | characterization + purge rg |

---

## Replacement / sunset (brownfield)

### A. Code / modules

| Устаревает (path / symbol) | Замена | Policy |
| :--- | :--- | :--- |
| `loop/runtime_adapters/dsh.py` · `DshAdapter` · `detect_dsh_model_mismatch` (если там) | Claude/Codex adapters only | delete in-epic |
| `loop/runtime_registry.yaml` key `dsh:` | keys `claude`, `codex` only | delete in-epic |
| `loop.epic_transition.get_dsh_preset` · kwargs `dsh_preset` · phase field `dsh_preset` | phase config without dsh preset | delete in-epic |
| `loop.prompt_builder` alias `deepseek-harness`/`deepseek`→`dsh` · runtime==`dsh` branches | normalize only claude/codex | delete in-epic |
| `loop.runner.config.load_project_environment` `runtime == "dsh"` / `DSH_HOOKS_BRIDGE` | non-dsh env only | delete in-epic |
| `loop.cli.runtime_sync` choices including `dsh` | choices `codex`,`claude`,`all`(=codex+claude) | delete in-epic |
| `loop.runtime.session_events` dsh-specific event normalize | generic/claude/codex only | delete in-epic |
| `loop.epic_transition` / arm path `epic_runtime == "dsh"` | remove branch | delete in-epic |
| `harness/hooks/dsh_stream_filter.py` | n/a | delete in-epic |
| `harness/hooks/session_resilience.py` DSH patterns / `detect_dsh_*` / imports from dsh adapter | claude/codex resilience only | delete in-epic |
| `harness/hooks/_lib.py` runtime frozenset including `dsh` · `DSH_HOOKS_BRIDGE` label | `{claude}` or claude+codex as designed | delete in-epic |
| `harness/hooks/epic/core.py` `dsh_preset` kwargs plumbing | remove | delete in-epic |
| `harness/manifest.yaml` `dsh:` blocks | remove | delete in-epic |
| `dsh/**` (entire tree: profiles, presets, plugins, patches, scripts, bin, README) | n/a | delete in-epic |
| `loop/tests/test_loop_dsh_dispatch.py` | n/a | delete in-epic |
| `loop/tests/test_dsh_e2e_smoke.py` | n/a | delete in-epic |
| Mixed tests asserting `runtime=="dsh"` / `DshAdapter` / `dsh_preset` / registry has dsh | rewrite deny or use claude/codex | delete in-epic / rewrite |
| `context_loop` allowlist globs requiring `dsh/` path class as first-class project surface | drop `dsh/` from path classes if only for DSH tree | delete in-epic |

### B. Entrypoints / deploy

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `bin/loop` case `claude\|codex\|dsh` | `claude\|codex` only | delete in-epic |
| `EPIC_RUNTIME=dsh` documented launch | unsupported | delete in-epic |
| `./dsh/scripts/install-profiles.sh` · `install-cc-hooks.sh` · `dsh/bin/which-dsh.sh` | n/a (tree gone) | delete in-epic |
| `runtime_sync --runtime dsh` / `all` including dsh | `all` = claude+codex | delete in-epic |
| Board/CLI `--runtime dsh` | choices without dsh | delete in-epic |

### C. Fallbacks / soft-fail

| Устаревает | Замена (fail-closed) | Policy |
| :--- | :--- | :--- |
| Silent dsh→claude when binary missing / profile invalid (legacy test scenarios) | raise / non-zero for unknown runtime; never substitute | delete in-epic |
| `DSH_HOOKS_BRIDGE` soft enable with claude paths | remove env branch | delete in-epic |
| Keeping registry key `dsh` «deprecated» | delete key | delete in-epic |
| Optional flag «allow_dsh» default off | FORBIDDEN | delete in-epic |

### I. Instruction surfaces

| Устаревает | Замена | Policy |
| :--- | :--- | :--- |
| `DSH.md` | delete file | delete in-epic |
| `docs/runbooks/dsh-loop-pilot.md` | delete | delete in-epic |
| `memory-bank/architecture/dsh-runtime.md` | delete; fix `architecture/index.md` links | delete in-epic |
| `AGENTS.md` / `CLAUDE.md` / `harness/instructions/main.md` DSH runtime bullet + DSH @file paragraph | Claude Code → CLAUDE.md; Codex → AGENTS.md only | delete in-epic (rewrite) |
| `README.md` agent table / DSH Runtime section | Claude + Codex only | delete in-epic |
| `LOOP-RUNTIMES.md` ## DSH section | remove; keep claude/codex | delete in-epic |
| `loop/README.md` / `loop/WORKFLOW.md` DSH mentions | rewrite | delete in-epic |
| `harness/instructions/spawn-hard.md` «Claude Code, Codex, DSH» | Claude Code, Codex, loop | delete in-epic |
| `docs/runbooks/codex-loop-pilot.md` cross-links to dsh pilot | remove dsh links | delete in-epic |

**Out of sunset (explicit keep):** historical `memory-bank/back/plan/T-HUB-*-dsh-*`, related qa/audit/events, roadmap `done:` rows naming old dsh epics, `memory-bank/back/roadmap/archive/*dsh*` — provenance; не rewrite в этом эпике.

---

<a id="qa-consumes"></a>
## QA consumes (test plan)

### Scope under test

- Epic surfaces: registry, adapters, CLI/env, `dsh/` absence, Kind I allowlist, targeted pytest.
- Out of scope for QA: historical memory-bank epic prose containing «dsh»; external installed `dsh` binary on host.

### Test matrix

| ID | Priority | Scenario | Command / fixture | Expected | Maps FR/AC |
|----|----------|----------|-------------------|----------|------------|
| TM-001 | P0 | `bin/loop` rejects dsh token | shell / unit wrapping case | exit ≠0 | FR-001, AC-3 |
| TM-002 | P0 | `EPIC_RUNTIME=dsh` fail-closed, no claude substitute | `bin/pytest` prepare/session tests | raise/non-zero; runtime_id ≠ claude success | FR-001, FR-009, AC− |
| TM-003 | P0 | registry load has no `dsh`; factory unknown | `bin/pytest loop/tests/test_runtime_registry.py` | PASS deny | FR-002, AC-1 |
| TM-004 | P0 | no module `loop.runtime_adapters.dsh`; `dsh/` gone | import + `test -d` / pytest | FAIL import; no dir | FR-003, FR-004, AC-2 |
| TM-005 | P0 | Kind I rg teaching patterns | `rg` allowlist | 0 hits | FR-008, AC-6 |
| TM-006 | P0 | no obsolete DSH test files; mixed rewritten | `bin/pytest` targeted set from decompose | PASS | FR-007, AC-5 |
| TM-007 | P1 | runtime_sync `all` = claude+codex only | `bin/pytest loop/tests/test_runtime_sync*.py` | PASS | FR-001, B |
| TM-008 | P1 | phase arm without `dsh_preset` / `get_dsh_preset` gone | `bin/pytest loop/tests/test_epic_transition.py` | PASS | FR-005 |

### Regression notes

- Не чинить suite восстановлением `DshAdapter`.
- Board sync tests с path `…/dsh/storages…` — заменить fixture paths.
- Full suite → BACK QA после IMPLEMENT (не в IMPLEMENT targeted).

## Review readiness

| Gate | Required | Status | Evidence |
|------|----------|--------|----------|
| CLARIFY / Product probe | L3 | done | clarify-20260916-dsh-full-purge.md |
| Eng review spine | L2+ | done | §Eng review spine |
| §0.11 counterparts (draft) | if external refs | done | registry↔adapters↔CLI listed in sunset |
| Delivery closure | yes | done | §Delivery closure vertical_slice |
| CREATIVE | no | n/a | — |
| qa_consumes draft | L2+ | done | ≥3 TM |
| Plan review batch | L2+ | done | §Plan review batch log |

## Plan review batch log

| Phase | Auto-resolved | Deferred (owner/next) | Taste / CRITICAL surfaced |
|-------|---------------|-------------------------|---------------------------|
| Product | History epic scrub out; live purge in; sole = claude+codex | — | none |
| Eng | Single epic vertical slice (not multi-epic): one outcome «DSH gone»; sNN ladder across trees | — | none |

## До DECOMPOSE (черновик нарезки)

Advisory band ~7–8 sNN (не cap):

1. `s01` — characterization + deny-oracle tests (red) for registry/CLI/env/`get_dsh_preset`
2. `s02` — registry cutover + delete `DshAdapter` module + factory deny
3. `s03` — loop call sites (config, prompt_builder, epic_transition, session_events, context_loop globs, runtime_sync, board CLI)
4. `s04` — harness purge (`dsh_stream_filter`, resilience, `_lib`, epic core, manifest)
5. `s05` — delete entire `dsh/` tree + `bin/loop` case
6. `s06` — Kind I docs rewrite/delete (`DSH.md`, runbooks, architecture, AGENTS/CLAUDE/README/LOOP-RUNTIMES/instructions)
7. `s07` — consolidate/rewrite mixed tests; delete `test_*dsh*`
8. `s08-legacy-fallback-purge` — full sunset_inventory A+B+C+I + grep_control (exclude historical epic trees from expect-0 if scoped; live paths expect 0)

## Appetite

| Поле | Значение | Описание |
| :--- | :--- | :--- |
| `timebox_days` | `3` | Live purge + Kind I |
| `cut_list` | `['history memory-bank epic scrub', 'host uninstall of global dsh binary']` | Вырезать первым при overrun |

## Следующий режим

→ **BACK DECOMPOSE** `T-HUB-106-dsh-runtime-full-purge` (после queue reconcile; если queue[0] ещё другой эпик — DECOMPOSE того; этот план готов к DECOMPOSE когда станет головой или по явной команде с id).
