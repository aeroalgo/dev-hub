# Аудит последних 15 сессий Claude Code vs заявленный workflow

**Дата снимка:** 2026-09-05  
**Источник сессий:** `~/.claude/projects/-home-aero-PyProject-dev-hub/*.jsonl` (mtime desc)  
**Канон сверки:** `CLAUDE.md` → `.claude/skills/role-command/SKILL.md` → `.cursor/rules/back_developer/workflow-*.mdc` → `finish-block.mdc` → `.claude/instructions/spawn-hard.md`  
**Текущий handoff на диске:** `memory-bank/activeContext.md` = `BACK ANALYZE` / `T-HUB-062-skill-topology-canonical-paths`  
**Смежный аудит кода:** [workflow-loop-20260905/index.md](./workflow-loop-20260905/index.md)

> Это **runtime/session** аудит: что агент и loop реально сделали в сессиях. Не путать с code-audit harness.  
> Текущая сессия `c0f2a42b-…` (этот отчёт) исключена из пятнашки.

---

## Короткий вердикт

Workflow **заявлен подробно**, но **исполняется с системными ложными зелёными путями**. За последние 15 сессий почти нет полного прохождения канона `ack → chain Read → work → verify JSON → mb-finish/finalize-step → один Handoff`.

Три независимых слоя врут одновременно:

1. **Loop/hooks** подсовывают агенту противоречивые команды (BUGFIX vs QA, DECOMPOSE vs ANALYZE, `verify OFF` vs `verify-decompose PASS`, `QA → REFLECT` после удаления REFLECT).
2. **Skill topology** не резолвится: workflow требует `@.agents/skills/<name>/SKILL.md`, файлы лежат в `.agents/skills/skills/<name>/`. Slash-skills `back-plan` / `back-decompose` тоже отсутствуют как файлы — `Skill` tool «успешен», инструкции не грузятся.
3. **Transient 401/503** превращают DECOMPOSE в retry-шторм: 8+ сессий с одним и тем же `resume_dirty`, без FINISH.

На диске сейчас рассинхрон: decompose T-HUB-062 **существует** (index + 5 sNN pending), `activeContext` уже зовёт **ANALYZE**, analyze-артефакта **нет**. T-HUB-060 QA = `verdict: fail`, bugfix-док пишет «1942 passed», queue уже ушёл на T-HUB-062.

---

## Канон, с которым сверяли (заявлено)

| Шаг | Что должно произойти | Источник |
|---|---|---|
| 0 | Role command → `Skill role-command` + `Skill back-<mode>` **если файл существует**; иначе полный Read chain | `role-command/SKILL.md`, CLAUDE.md HARD RULE |
| Ack | `OK {PREFIX} {MODE} — начинаю`; PLAN/DECOMPOSE — `SUSPENSION GUARD` | role-command Acknowledgement |
| Chain | `CLAUDE.md` → `mainrule.mdc` → role index/core → `workflow-{mode}.mdc` → Gates `_lean/{mode}.mdc` → `@` до листьев | CLAUDE.md HARD RULE |
| Skills | только пути из workflow / `skills.impl` шага; **literal path exists** | workflow-decompose §Skills; T-HUB-062 plan |
| Session load | `activeContext.load_now` only; ONE shard | Session start |
| IMPLEMENT | seed → flush cp → suite → evidence `in_progress` → validate-step → Handoff → `@verify-implement` fenced JSON → PASS → `finalize-step` / `mb-finish implement` | finish-block |
| DECOMPOSE | index coverage 4 секции + yaml steps → `validate-decompose-tree` → `@verify-decompose` → `mb-finish decompose`; next = **ANALYZE only** | workflow-decompose 7a/7b |
| ANALYZE | read-only artifact `analyze-*.yaml`, `critical_count=0` до IMPLEMENT | workflow-analyze |
| QA | full `bin/pytest -q --tb=line` + `qa-*.yaml` + `@verify-qa` + Handoff; next **не REFLECT** | workflow-qa; T-HUB-060 WHAT |
| BUGFIX | QA source → root cause → red/green → `@verify-bugfix` → `mb-finish bugfix` | workflow-bugfix |
| Spawn | packed ALLOW; FRONT tests parent-only HARD RULE в prompt | spawn-hard |

---

## Пятнашка (mtime desc, без текущей)

| # | Session | mtime (UTC+≈) | Размер | Тип | Команда (user/loop) | Итог vs канон |
|---|---------|---------------|--------|-----|---------------------|---------------|
| 1 | `ebccfa0d` | 22:32 | 128K | IDE human | OmniRoute 401 / docker logs | **не role-command** — диагностика API |
| 2 | `78283c81` | 22:31 | 1.3M | loop epic | `BACK DECOMPOSE` T-HUB-062 + resume_dirty 401 | Ack + Skill; **нет mb-finish**; SessionStart влил **весь plan.md**; spawn-gate: `verify/reviewer OFF` |
| 3 | `c2cb1ce8` | 21:52 | 149K | IDE human | OmniRoute 401 | **не workflow** |
| 4 | `5f623711` | 21:49 | 2.2M | IDE human | `BACK PLAN` по audit | Ack + `SUSPENSION GUARD` + Skill `back-plan`+`role-command`; **skill file missing**; multi-epic в queue — PLAN слой сработал как продукт, **не как исполняемый skill path** |
| 5 | `d0624c66` | 21:48 | 78K | loop | `BACK DECOMPOSE` resume 401 | **аборт до работы** |
| 6 | `7cf390c6` | 21:45 | 78K | loop | то же | **аборт** |
| 7 | `33eb8c25` | 21:44 | 78K | loop | то же | **аборт** |
| 8 | `fcf79a64` | 21:43 | 78K | loop | то же | **аборт** |
| 9 | `6c73ccc7` | 21:20 | 78K | loop | то же | **аборт** |
| 10 | `eb1e7395` | 21:19 | 78K | loop | то же | **аборт** |
| 11 | `82a804c4` | 21:19 | 78K | loop | то же | **аборт** |
| 12 | `ff88ad04` | 21:18 | 79K | loop | DECOMPOSE resume **503** | **аборт** |
| 13 | `b47bb588` | 21:17 | 518K | loop | `BACK DECOMPOSE` (без dirty) | SessionStart влил plan; spawn-gate `verify OFF`; **двойной SessionStart** (`.claude/hooks` и `harness/hooks`) |
| 14 | `9ccc0a04` | 20:15 | 76K | loop | `BACK DECOMPOSE` | **аборт / короткий** |
| 15 | `94cea2d3` | 20:14 | 417K | loop | user=`BACK BUGFIX` T-HUB-060 | **P0: SessionStart inject = `COMMAND: BACK QA`**, step=`unknown`; spawn-gate: **QA FINISH → REFLECT** |

Дополнительно (чуть старше 15, нужны для цепочки T-HUB-060):

| Session | Команда | Наблюдение |
|---------|---------|------------|
| `7bdabfca` | `BACK BUGFIX` | SessionStart phase=`BUGFIX` но `step: unknown` |
| `d0f570f0` | `BACK QA` | QA после AUDIT; load_now = audit.yaml (не qa artifact на входе — ок для старта QA) |
| `82d02f14` | `BACK AUDIT` | resume_dirty **fatal** `malformed stream-json`; `step: unknown` |
| `ed0d31d9` | `BACK IMPLEMENT s05` | FIX INCOMPLETE + checkpoint_trace; explorer managed **off**; next `mb-finish implement` |

---

## Разбор по шагам workflow (что сломано)

### 1. Acknowledgement — частично работает

- `5f623711` (PLAN): `OK BACK PLAN — начинаю` + `SUSPENSION GUARD active — plan output unlimited` — **соответствует** role-command.
- `78283c81` (DECOMPOSE): `OK BACK DECOMPOSE — начинаю` — **нет** обязательного `SUSPENSION GUARD active — decompose output unlimited` (role-command: DECOMPOSE тоже guard).
- Abort-сессии 78K: ack отсутствует — сессия умерла на API.

**FAIL:** DECOMPOSE guard не печатается стабильно.  
**OK:** PLAN ack+guard в IDE-сессии.

### 2. Skill tool / role-command chain — заявлено ≠ диск

Заявлено: `Skill` грузит `.claude/skills/<name>/SKILL.md`.

Факт:

| Path | Exists? |
|------|---------|
| `.claude/skills/role-command/SKILL.md` | да (эта сессия его прочитала) |
| `.claude/skills/back-plan/SKILL.md` | **нет** |
| `.claude/skills/back-decompose/SKILL.md` | **нет** |
| `harness/claude/skills/back-plan/SKILL.md` | **нет** |
| `.agents/skills/writing-plans/SKILL.md` | **нет** |
| `.agents/skills/skills/writing-plans/SKILL.md` | **да** |

Сессии `5f623711` и `78283c81` всё равно вызывают `Skill back-plan` / `Skill back-decompose`. Tool возвращает `Launching skill: back-plan` / success. Агент **не получает тело skill** и идёт в импровизацию + частичный Read.

Это ровно P0 из [02-workflow-pack-and-rules.md](./workflow-loop-20260905/02-workflow-pack-and-rules.md): главный read-contract не исполняется.

**FAIL:** Step 0b HARD RULE «прочитай skill path» неисполним для workflow skills и для Claude Code role skills `back-*`.

### 3. HARD READ chain vs SessionStart inject

Заявлено (CLAUDE.md): до основной работы полный Read chain.  
Заявлено (loop prompt): «HARD READ: прочитай **только** указанный entrypoint» + mainrule.

Конфликт **внутри одного prompt**:

- Loop: «только CLAUDE.md, потом mainrule, потом chain».
- CLAUDE.md: «нельзя начинать, пока не прочитана **вся** цепочка рекурсивно».
- Token-economy: lean load, `load_now` only.
- SessionStart: **инлайнит весь `plan.md`** в additionalContext (T-HUB-062 plan — сотни строк). Это нарушает lean load IMPLEMENT/DECOMPOSE и раздувает контекст до работы.

На DECOMPOSE это ещё и **ложный «файл уже в контексте»**: агент может не Read-ить plan с диска и пропустить поздние правки.

**FAIL:** SessionStart = полный plan dump, не `load_now` paths.  
**FAIL:** prompt говорит «только entrypoint», CLAUDE.md говорит «вся цепочка» — агент выбирает случайно.

### 4. Duplicate hooks (наблюдаемо в jsonl)

`.claude/settings.json` вешает **два** SessionStart и **два** UserPromptSubmit:

```text
python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.py"
python3 "$CLAUDE_PROJECT_DIR/harness/hooks/session-start.py"
```

В сессиях это видно:

- `b47bb588`: command = `.claude/hooks/session-start.py`
- `78283c81`: command = `harness/hooks/session-start.py`
- `94cea2d3`: **оба** SessionStart подряд (duration 868ms и 930ms), UserPromptSubmit spawn-gate **дважды** с одинаковым текстом.

`.claude/hooks/session-start.py` — тот же код (alongside install), но runtime запускает **два процесса**. Следствия: двойной inject, гонка fingerprint, дубль spawn-gate, возможные двойные state writes (P1 в code-audit).

**FAIL относительно заявленного «один hook на event».** Это T-HUB-065, но уже ломает текущие сессии.

### 5. Projection / phase mismatch (P0 runtime)

| Сессия | Loop user COMMAND | SessionStart additionalContext COMMAND | step |
|--------|-------------------|----------------------------------------|------|
| `94cea2d3` | `BACK BUGFIX` | **`BACK QA`** | `unknown` |
| `7bdabfca` | `BACK BUGFIX` | `BACK BUGFIX` | `unknown` |
| `d0f570f0` | `BACK QA` | `BACK QA` | `unknown` |
| `82d02f14` | `BACK AUDIT` | `BACK AUDIT` | `unknown` |
| `ed0d31d9` | `BACK IMPLEMENT` s05 | `BACK IMPLEMENT` s05 | s05 (ок) |
| `78283c81` | `BACK DECOMPOSE` | `BACK DECOMPOSE` | DECOMPOSE |

`94cea2d3` — агент получил **две разные фазы в одном ходе**. Дальше spawn-gate ещё пишет `PROJECTION phase=QA` и `QA FINISH → REFLECT`, хотя user/loop требовал BUGFIX, а эпик T-HUB-060 **удалил REFLECT**.

`step: unknown` на QA/BUGFIX/AUDIT = projection не читает armed step из state. Агент не знает, какой artifact закрывать.

**FAIL:** `session_start_payload` / activeContext fingerprint расходится с loop COMMAND. Это не «агент не прочитал rules» — **harness врёт фазу**.

### 6. Spawn-gate stale canon (REFLECT + verify OFF)

Одинаковый inject во всех loop-сессиях:

```text
QA FINISH: qa-*.yaml (verdict) + Handoff → REFLECT обязательны.
armed_step=DECOMPOSE → verify/reviewer OFF (docs-only).
FINISH после decompose/index.*; promote DECOMPOSE→IMPLEMENT на prepare.
```

Канон сейчас:

- T-HUB-060 / `POST_IMPLEMENT_CHAIN` = `IMPLEMENT → AUDIT → QA → EPIC_DONE` (**без REFLECT**).
- `workflow-decompose.mdc` 7a: promote → **`@verify-decompose`** → next **BACK ANALYZE only**. **FORBIDDEN** IMPLEMENT без ANALYZE.
- Loop DECOMPOSE prompt сам требует: `validate-decompose-tree` + **verify-decompose PASS** + `mb-finish decompose`.

Итого на DECOMPOSE агент читает:

1. Prompt: нужен verify-decompose PASS.  
2. Spawn-gate: verify **OFF**, promote сразу в IMPLEMENT.  
3. workflow-decompose.mdc: ANALYZE hard gate.

Это три взаимоисключающих инструкции. Агент не может «правильно» закрыть DECOMPOSE.

**FAIL:** UserPromptSubmit overlay не синхронизирован с phase_registry после T-HUB-060.  
**FAIL:** DECOMPOSE verify выключен overlay, хотя spawn-hard и workflow его требуют.

### 7. DECOMPOSE T-HUB-062 — артефакты vs FINISH

На диске есть:

- `md/plan.md`
- `md/decompose-index.md` (coverage-таблицы на месте)
- `yaml/decompose-index.yaml` — 5 steps, все **`pending`**
- `yaml/steps/s01…s05-*.yaml` (s01 прочитан: полный `plan_contract` / goal / skills)

Нет:

- `memory-bank/back/analyze/T-HUB-062-…/analyze-*.yaml`
- признака `mb-finish decompose` в последних abort-сессиях
- `validate-decompose-tree` evidence в abort jsonl (78K файлы = queue + prompt, почти без assistant work)

`activeContext.md` уже:

```text
mode: ANALYZE
step_id: ANALYZE
load_now: plan.md + yaml/index.yaml  (путь в тексте: decompose-index.yaml)
```

Канон ANALYZE: вход **после FINISH DECOMPOSE**. Если mb-finish отработал в сессии, которая не попала в пятнашку / оборвалась после write — handoff есть, **promote-gate неполный**:

- index steps всё ещё `pending` (для DECOMPOSE это нормально: status шагов = IMPLEMENT, не DECOMPOSE-complete flag).
- **нет analyze artifact**, но handoff уже ANALYZE.
- IMPLEMENT workflow: без `critical_count=0` → **REJECT**.

**Частичный PASS:** нарезка 5 sNN + coverage секции выглядят по канону maximal detail.  
**FAIL FINISH:** нет закрытого verify-decompose JSON; ANALYZE armed без analyze file; 8 retry-сессий не довели mb-finish.

`resume_dirty` всегда указывает **только** `plan.md`, хотя dirty на самом деле index+steps. Правило «Read dirty_files first» **не видит** yaml tree → риск перезаписать decompose или «продолжить plan».

**FAIL:** dirty_files неполный (не трекает yaml/steps).

### 8. IMPLEMENT s05 T-HUB-060 (`ed0d31d9`)

Заявлено: seed → cp flush → suite → validate-step → Handoff → verify-implement → mb-finish.

Факт prompt:

- implement yaml `status: in_progress`, все cp **pending**
- `FIX INCOMPLETE (HARD)` — правильно блокирует закрытие
- `explorer managed: off` — parent graphify+rg; это **осознанный bypass** spawn-hard explorer
- skills.impl шага = `.agents/skills/tdd/SKILL.md` — **файла нет** (nested only)

Index сейчас s01–s05 **completed** → какой-то последующий ход закрыл s05. В пятнашке нет сессии с явным `loop-gate-verdict` verify-implement (jsonl IMPLEMENT обрезан Read-ом, полный 538K). Риск: finalize без packed verify, если stop-gate был soft.

**Не доказан PASS verify-implement** по доступному префиксу jsonl.

### 9. QA / BUGFIX T-HUB-060

Канон QA: full suite + qa yaml + `@verify-qa` + Handoff next BUGFIX при fail.

Факт на диске:

- `qa-20260905-remove-reflect-phase.yaml` — `verdict: fail`, ISS-001/002, suite `bin/pytest -q --tb=line`
- bugfix md утверждает **full suite 1942 passed**
- qa yaml **не обновлён** на pass после bugfix
- `activeContext` уже не T-HUB-060, а T-HUB-062 ANALYZE
- queue.yaml: T-HUB-060 нет в `queue:` (ушёл дальше)

Канон после QA fail: BUGFIX → re-QA (full suite) → pass → DONE/AUDIT chain.  
Факт: bugfix-док есть, **повторного QA yaml нет**, эпик считается ушедшим.

Spawn-gate на QA/BUGFIX сессиях всё ещё требует **REFLECT**. Если агент послушал overlay — пытался бы писать reflection artifact, который lifecycle больше не принимает. Если послушал T-HUB-060 — overlay = FAIL.

Session `94cea2d3`: BUGFIX prompt vs QA inject = агент мог «закрыть QA» повторно или не вызвать `mb-finish bugfix`.

**FAIL:** QA artifact stale fail при заявленном green suite.  
**FAIL:** нет видимого `@verify-bugfix` / `@verify-qa` fenced JSON в просмотренных префиксах.  
**FAIL:** overlay REFLECT vs удалённая фаза.

### 10. Graphify

Role-command: graphify обязателен для IMPLEMENT/BUGFIX/QA, **пропуск для PLAN/DECOMPOSE**.

Пятнашка почти вся PLAN/DECOMPOSE/abort — пропуск graphify **легален**.  
IMPLEMENT/BUGFIX сессии: в префиксах jsonl graphify не виден; для BUGFIX это **вероятный FAIL** Step 0.

### 11. Transient abort loop (операционный FAIL)

8 сессий подряд:

```text
prev_session: aborted — API Error: 401 [claude] All 1 connection(s) banned
abort_kind: transient
continue_from_checkpoint: DECOMPOSE
dirty_files: plan.md
```

Loop считает 401 **transient** и ретраит до 30 раз. OmniRoute ban — не «подожди 20s», это **нужен reconnect**, не ещё 8 пустых jsonl по 78KB.

**FAIL относительно заявленного resume:** dirty не прогрессирует, checkpoint DECOMPOSE не имеет cp-файла, каждая сессия заново жрёт SessionStart+plan dump.

IDE-сессии `ebccfa0d` / `c2cb1ce8` — человек уже чинил 401 снаружи loop. Loop это не остановил.

### 12. PLAN `5f623711` — что сработало

Единственная сессия пятнашки, где human role-command прошёл «как в Cursor»:

- ack + suspension guard
- Skill role-command + back-plan (даже если файл back-plan отсутствует)
- результат на диске: 8 планов T-HUB-062…069 + `queue.yaml` batch `workflow-loop-20260905` + clarify
- tasks/log: `BACK PLAN MULTI-EPIC (8)`

Это **соответствует** `workflow-plan-multi-epic.mdc` (не mega-plan).  
Не доказано: полный Read chain до листьев; `wc -l` plan acceptance перед FINISH; inline roadmap-merge vs отдельная команда.

---

## Матрица «заявлено → факт»

| Правило | Статус в пятнашке | Доказательство |
|---------|-------------------|----------------|
| `OK PREFIX MODE` | частичный | PLAN/крупный DECOMPOSE да; abort — нет |
| DECOMPOSE suspension guard | **нет** | `78283c81` ack без guard |
| Skill `back-*` существует | **FAIL** | Read → File does not exist |
| `@.agents/skills/<name>/SKILL.md` | **FAIL** | nested `skills/skills/` only |
| Один SessionStart | **FAIL** | settings.json ×2; jsonl ×2 |
| SessionStart phase = loop COMMAND | **FAIL** | `94cea2d3` BUGFIX vs QA |
| `step` не unknown | **FAIL** на QA/AUDIT/BUGFIX | inject `step: unknown` |
| DECOMPOSE `@verify-decompose` | **FAIL overlay** | spawn-gate verify OFF |
| DECOMPOSE next = ANALYZE | **рассинхрон** | overlay: IMPLEMENT; workflow: ANALYZE; AC: ANALYZE без artifact |
| QA next ≠ REFLECT | **FAIL overlay** | «REFLECT обязательны» после T-HUB-060 |
| `mb-finish` после PASS | не видно в abort DECOMPOSE | 78K jsonl |
| `finalize-step` не руками | не проверено на s05 полностью | index completed, jsonl prefix без verdict |
| load_now lean | **FAIL SessionStart** | полный plan.md inline |
| dirty_files полнота | **FAIL** | только plan.md при yaml dirty |
| 401 = transient retry | **FAIL ops** | 8 пустых DECOMPOSE |
| FRONT tests parent-only | n/a | нет FRONT сессий |
| TodoWrite ≤2 | не измерено | не главный дефект |

---

## Корневые причины (не симптомы)

1. **Несколько SoT на одну фазу:** loop prompt, SessionStart projection, UserPromptSubmit spawn-gate, workflow mdc, activeContext. Они расходятся → любой агент «ломает workflow», даже послушный.
2. **Skill FS layout** (T-HUB-062 как раз про это) ломает Step 5 **прямо сейчас**, включая текущий ANALYZE/будущий IMPLEMENT: `skills.impl` указывает на несуществующий path.
3. **Alongside duplicate hooks** (T-HUB-065) уже в production settings, не в бэклоге «потом».
4. **Незавершённый T-HUB-060:** code/tests почистили REFLECT, **prompt overlay и QA yaml — нет**.
5. **Abort classifier:** 401 ban классифицирован как TRANSIENT → шторм сессий вместо HALT/`NEED_HUMAN`.

---

## Что сейчас на диске (истина для оператора)

| Эпик | Заявлено loop/AC | Факт артефактов | Можно ли продолжать канон |
|------|------------------|-----------------|---------------------------|
| T-HUB-060 | ушёл из queue | QA fail yaml + bugfix «green» без re-QA yaml | **не закрыт по QA канону** |
| T-HUB-062 | AC = ANALYZE | decompose tree есть; **analyze yaml нет**; skills канон всё ещё nested | ANALYZE можно, IMPLEMENT **нельзя** (нет analyze + skills 404) |
| T-HUB-063…069 | queue pending | планы с PLAN-сессии | ждут DECOMPOSE после 062 |

Рекомендуемый ручной порядок (не делать в этом отчёте):

1. Починить OmniRoute 401 **до** следующего `epic-run` (иначе снова 8 пустых DECOMPOSE).
2. Не стартовать IMPLEMENT 062, пока нет `analyze-*.yaml` с `critical_count=0`.
3. Считать overlay `QA → REFLECT` и `DECOMPOSE verify OFF` **известным багом harness**, не ошибкой агента.
4. T-HUB-065 (duplicate hooks) и T-HUB-062 (skill paths) — блокеры исполнения workflow, не «потом в batch».

---

## Метод и ограничения этого аудита

- Взяты 15 jsonl по mtime; текущая сессия исключена.
- Крупные файлы (1.3M / 2.2M) читались префиксами (первые assistant tool_use + SessionStart stdout). Полный token-by-token verify JSON по 2MB **не** разбирался.
- Bash/Write в `/tmp` в этой сессии блокировались classifier’ом (`cc/claude-sonnet-4-6 temporarily unavailable`) — нет автоматического grep по всем 15 jsonl; сигналы сняты Read префиксов + артефакты memory-bank.
- Code-level findings дублируют workflow-loop-20260905, если они **проявились в сессиях**; новые — phase mismatch, abort storm, ANALYZE без artifact, stale QA yaml.

---

## Связанные файлы

- Сессии: `~/.claude/projects/-home-aero-PyProject-dev-hub/`
- [activeContext.md](../activeContext.md)
- [queue.yaml](../back/roadmap/queue.yaml)
- [T-HUB-062 decompose-index.yaml](../back/plan/T-HUB-062-skill-topology-canonical-paths/yaml/decompose-index.yaml)
- [T-HUB-060 qa.yaml](../back/qa/T-HUB-060-remove-reflect-phase/qa-20260905-remove-reflect-phase.yaml)
- [settings.json hooks](../../.claude/settings.json)
- [spawn-hard.md](../../.claude/instructions/spawn-hard.md)
