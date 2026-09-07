# Workflow Read Chain Audit — сокращение Read агента

**Дата:** 2026-09-07  
**Цель:** найти паттерны дублирования в цепочках чтения workflow-файлов и дать конкретные рекомендации по объединению.  
**Роли:** back_developer / front_developer / integration_developer

---

## Ключевые паттерны (универсальные для всех ролей)

### Паттерн 1 — W + L = два Read вместо одного

**Суть:** Каждая команда грузит `workflow-<mode>.mdc` (W) + `isolation_rules/_lean/<mode>.mdc` (L). L — gates-checklist, который является сокращённым подмножеством W. Агент читает оба файла, но L не добавляет уникального контента.

**Данные (BACK):**

| Команда | W (строк) | L (строк) | L < W? | Read можно сэкономить |
|---|---|---|---|---|
| REFLECT | 29 | 29 | = | да — слить L→W |
| TASK | 24 | 20 | да | да — слить L→W |
| BUGFIX | 18 | 24 | нет | да — слить L→W |
| ROADMAP-MERGE | 23 | 17 | да | да — слить L→W |
| ARCHIVE | 24 | 30 | нет | да — слить L→W |
| CREATIVE | 75 | 28 | да | да — слить L→W |
| REFACTOR | 32 | 27 | да | да — слить L→W |
| ANALYZE | 62 | 30 | да | да — слить L→W |
| CLARIFY | 91 | 29 | да | да — слить L→W |
| VAN | 27 | 34 | нет (L > W) | L > W — W thin-wrapper |
| QA | 28 | 51 | нет (L > W) | L > W — W thin-wrapper |
| IMPLEMENT | 44 | 55 | нет (L > W) | L > W — W thin-wrapper |
| DECOMPOSE | 64 | 32 | да | да — слить L→W |
| PLAN | 60 | 42 | да | да — слить L→W |
| SECURITY | 70 | 43 | да | да — слить L→W |
| AUDIT | 67 | 37 | да | да — слить L→W |

**Инвертированный вариант (L > W):** QA, IMPLEMENT, VAN — здесь W является thin-wrapper над L. W можно удалить, оставив только L (переименовать в W).

**Итог паттерна:** 16 пар → 16 сэкономленных Read на каждую сессию × 3 роли = **48 Read за цикл** при слиянии.

---

### Паттерн 2 — mainrule-core = отдельный Read на каждую сессию

**Суть:** `mainrule-core.mdc` читается первым в каждой сессии каждой роли. 60 строк (BACK), 34 строки (FRONT), 53 строки (INTEG). Контент — 3-4 общих политики.

**Данные:**
- BACK mainrule-core: 60 строк
- FRONT mainrule-core: ~34 строки (90% совпадает с BACK)
- INTEG mainrule-core: ~53 строки (60% совпадает с BACK)

**Рекомендация:** вклеить mainrule-core контент в конец каждого W-файла. Это устраняет 1 Read на сессию. При слиянии с Паттерном 1 (W+L) — mainrule-core попадает в единый файл автоматически.

**Оверхед:** +60 строк в каждый W-файл (15 команд × 3 роли = 45 файлов). Но Read сокращается с 3 до 1 в начале сессии.

---

### Паттерн 3 — cheatsheet + W + L = тройная нагрузка

**Суть:** 4 команды имеют cheatsheet (AUDIT, DECOMPOSE, IMPLEMENT, PLAN). Агент читает: C (hot path) + L (gates) + W (full, при FAIL). Три файла про одно.

| Команда | C (строк) | W (строк) | L (строк) | Итого |
|---|---|---|---|---|
| DECOMPOSE | 19 | 64 | 32 | 115 → 1 файл |
| IMPLEMENT | 24 | 44 | 55 | 123 → 1 файл |
| PLAN | 17 | 60 | 42 | 119 → 1 файл |
| AUDIT | 17 | 67 | 37 | 121 → 1 файл |

**Рекомендация:** слить C + L + mainrule-core в конец W. Один файл с секциями:
```
# BACK DECOMPOSE
## Hot path (cheatsheet)
## Full workflow
## Gates (из _lean)
## Policies (из mainrule-core)
```

**Итог паттерна:** 4 команды × 3 роли = 12 файлов → 4 файла = **-8 Read** только на cheatsheet.

---

### Паттерн 4 — двойные ссылки на shared внутри одного W

**Суть:** один и тот же shared-файл упоминается в W несколько раз. Агент может интерпретировать каждое упоминание как отдельный Read.

| W-файл | Shared-файл | Упоминаний |
|---|---|---|
| workflow-decompose (все 3 роли) | `workflow-behavior-first.mdc` | 3× |
| workflow-decompose (все 3 роли) | `workflow-legacy-fallback-cleanup.mdc` | 2× |
| workflow-analyze (все 3 роли) | `workflow-analyze-core.mdc` | 2× |
| workflow-clarify (все 3 роли) | `workflow-clarify-core.mdc` | 2× |
| workflow-plan (all) | `workflow-plan-clarify-orchestration.mdc` | 2× |

**Рекомендация:** в каждом W оставить ровно одно упоминание shared-файла. Заменить множественные `@shared/X` на одну ссылку `@shared/X` в шапке с пометкой §section.

---

### Паттерн 5 — транзитивные дубли (A→B, и B в W тоже напрямую)

**Суть:** shared-файл A ссылается на shared-файл B изнутри себя, и одновременно B упомянут напрямую в W. Агент читает B дважды — через A и напрямую.

**Топ транзитивных петель:**

| Workflow | Прямая ссылка | Транзитив через | Дубль |
|---|---|---|---|
| DECOMPOSE (все 3) | `workflow-behavior-first` | `workflow-legacy-fallback-cleanup` | взаимная петля |
| DECOMPOSE (все 3) | `workflow-legacy-fallback-cleanup` | `workflow-behavior-first` | взаимная петля |
| PLAN (все 3) | `workflow-plan-clarify-orchestration` | `workflow-plan-outcome-prompt` | outcome-prompt лишний напрямую |
| VAN (все 3) | `workflow-van-brownfield` | `memory-bank-paths` | взаимная петля |
| CLARIFY (все 3) | `workflow-plan-clarify-orchestration` | `workflow-clarify-core` | clarify-core лишний напрямую |
| REFACTOR (все 3) | `workflow-refactor-epic` | `finish-block` | finish-block лишний напрямую |

**Рекомендация:** убрать прямую ссылку из W на B если A уже тянет B транзитивно. Или наоборот — убрать ссылку на A из W если нужен только B.

---

### Паттерн 6 — мёртвые и нулевые файлы

Файлы с 0 прямых ссылок из workflow-файлов ролей:

| Файл | Строк | Статус |
|---|---|---|
| `shared/workflow-idea-pipeline.mdc` | 205 | не используется ни одной ролью |
| `shared/test-timeout.mdc` | 53 | 0 прямых ссылок |
| `shared/visual-maps/idea-pipeline-mode-map.mdc` | 72 | только через idea-pipeline (тоже 0) |
| `shared/context-session-economy.mdc` | 56 | только через idea-pipeline |
| `shared/finish-doc-router.mdc` | 50 | только транзитивно через finish-block |
| `shared/cheatsheets/back-audit.mdc` | 17 | мёртвый артефакт, 0 ссылок |

**Рекомендация:** `back-audit.mdc` удалить. Остальные — проверить актуальность.

---

## Топ shared-файлов по нагрузке (строк × число потребителей)

| # | Файл | Строк | Потребителей | Score |
|---|---|---|---|---|
| 1 | `workflow-legacy-fallback-cleanup` | 260 | 10 | 2600 |
| 2 | `finish-block` | 83 | 24 | 1992 |
| 3 | `workflow-behavior-first` | 250 | 7 | 1750 |
| 4 | `epic-scoped-paths` | 118 | 10 | 1180 |
| 5 | `workflow-plan-clarify-orchestration` | 106 | 6 | 636 |
| 6 | `workflow-plan-outcome-prompt` | 119 | 4 | 476 |
| 7 | `workflow-clarify-core` | 151 | 3 | 453 |
| 8 | `workflow-spec-first-replace` | 106 | 4 | 424 |
| 9 | `workflow-security-epic` | 111 | 3 | 333 |
| 10 | `workflow-van-brownfield` | 104 | 3 | 312 |

`finish-block` (83 строки, 24 потребителя) — самый высокочастотный. Читается перед каждым FINISH во всех режимах. Это оправдано — он нужен всем. Не кандидат на inline.

`workflow-legacy-fallback-cleanup` (260 строк, 10 потребителей) — самый тяжёлый. DECOMPOSE, PLAN, QA, AUDIT — читают его все. Его нельзя инлайнить везде, но можно сократить сами ссылки устранив транзитивные дубли.

---

## Сводка рекомендаций (приоритет)

### P0 — cheatsheet → W (самый высокий ROI, минимальный риск)

**Эффект:** -1 Read для DECOMPOSE, IMPLEMENT, PLAN, AUDIT.  
**Почему не _lean→W сначала:** аудит показал что _lean содержит контент отличный от W — это gates-as-contract (pass/fail условия, abort-блок, level delta таблица), а W — process-as-instructions. _lean загружается всегда на старте, W только при FAIL. Если вклеить _lean в конец W, агент будет читать весь процессный текст каждый раз когда нужна только gate-проверка — экономия файла будет съедена ростом загружаемого контента.  
**Работа:** перенести содержимое `cheatsheets/back-*.mdc` в блок `## Hot path` в начало соответствующего W-файла. Удалить cheatsheet файлы.  
**Список:** `cheatsheets/back-decompose.mdc` → `workflow-decompose.mdc`; `cheatsheets/back-implement.mdc` → `workflow-implement.mdc`; `cheatsheets/back-plan.mdc` → `workflow-plan.mdc`; `cheatsheets/integ-plan.mdc` → `integration_developer/workflow-plan.mdc`.

### P1 — дубли в _lean между ролями → shared

**Эффект:** -2 файла (сейчас 3 одинаковых файла, станет 1 shared).  
**Данные:** `roadmap-merge.mdc` — полный дубль во всех трёх ролях (diff exit 0). `security.mdc` — 43 строки × 3 роли, дельта 1 строка на роль. `van.mdc` — BACK=INTEG полный дубль.  
**Работа:** переместить `_lean/roadmap-merge.mdc` в `shared/_lean/roadmap-merge.mdc`, обновить ссылки. Для `security.mdc` — вынести общий контент в shared, добавить 1-строчный role-patch.

### P2 — mainrule-core: выделить shared-ядро, сократить role-файлы

**Не вклеивать в каждый W** — это +2 578 строк дублирования и 52 места для правки вместо 1.  
**Правильная стратегия:** вынести общий контент (~10–12 строк: MEMORY BANK структура, ФОРМАТ, pytest runner) в `shared/mainrule-shared.mdc`. Оставить в каждом role-файле только уникальный контент: BACK ~40 строк (УРОВНИ, flowchart переходов, promote DECOMPOSE→IMPLEMENT), FRONT ~18 строк (DESIGN STACK, visible_ui, Vitest rule), INTEG ~35 строк (ELEMENT-FIRST, CONTRACT, GAP fanout).  
**Эффект:** mainrule-core с 34–60 строк → 15–20 строк уникального контента. 1 Read на сессию остаётся, но файл легче.

### P3 — устранить двойные ссылки на shared внутри W

**Эффект:** устраняет риск двойного Read одного файла.  
**Работа:** в каждом W заменить множественные `@shared/X` на одну ссылку в шапке. Занимает 10–15 минут на файл.  
**Приоритет файлов:** `workflow-behavior-first` (3× в DECOMPOSE), `workflow-analyze-core` (2× в ANALYZE), `workflow-plan-clarify-orchestration` (2× в PLAN).

### P3 — устранить двойные ссылки на shared внутри W

**Эффект:** устраняет риск двойного Read одного файла.  
**Работа:** в каждом W заменить множественные `@shared/X` на одну ссылку в шапке. Занимает 10-15 минут на файл.  
**Приоритет файлов:** `workflow-behavior-first` (3× в DECOMPOSE), `workflow-analyze-core` (2× в ANALYZE), `workflow-plan-clarify-orchestration` (2× в PLAN).

### P4 — устранить транзитивные петли

**Эффект:** -1 Read в DECOMPOSE, VAN, CLARIFY, REFACTOR.  
**Работа:** в каждом проблемном W убрать прямую ссылку на B если она уже идёт транзитивно через A.  
**Список:** см. Паттерн 5 выше.

### P5 — удалить мёртвые файлы

**Работа:** удалить `cheatsheets/back-audit.mdc`. Остальные 5 нулевых файлов — проверить вручную перед удалением.

---

## Оценка суммарного эффекта (если применить P0+P1+P2+P3)

| Команда (пример BACK) | Read сейчас | Read после |
|---|---|---|
| REFLECT | 3 (W+L+mainrule) | 1 |
| BUGFIX | 3 | 1 |
| TASK | 3 | 1 |
| QA | 3 | 1 |
| ANALYZE | 4 | 2 (W + workflow-analyze-core) |
| DECOMPOSE | 7–8 | 4–5 (W + behavior-first + legacy + epic-scoped-paths) |
| PLAN | 9–10 | 5–6 (W + legacy + spec-first + multi-epic + outcome-prompt) |
| IMPLEMENT | 5 + N skills | 3 + N skills (W + scope-lock + finish-block) |

Простые команды (REFLECT, BUGFIX, TASK): **с 3 до 1 Read** — снижение на 67%.  
Сложные (DECOMPOSE, PLAN): **с 8–10 до 4–6 Read** — снижение на 40–50%.

---

## Что НЕ объединять

| Файл | Причина оставить |
|---|---|
| `finish-block.mdc` | 24 потребителя, нужен только перед FINISH — правильно грузить lazy |
| `workflow-legacy-fallback-cleanup.mdc` | 260 строк × 10 команд — inline везде = +2600 строк в репо |
| `workflow-behavior-first.mdc` | то же — 250 строк × 7 команд = +1750 строк |
| `shared/workflow-analyze-core.mdc` | используется всеми тремя ролями — правильный shared |
| Все SKILL.md | загружаются по-шагово, не все сразу — это уже правильная lazy-загрузка |
 Строки shared-файлов и количество ссылок по ролям
Shared-файл	Строк	back	front	integ	Итого refs (workflow-файлов)	refs из shared
workflow-legacy-fallback-cleanup	260	5	4	4	10	2
workflow-behavior-first	250	5	4	4	7	7
workflow-idea-pipeline	205	0	0	0	0	0
workflow-clarify-core	151	2	1	1	3	1
workflow-plan-outcome-prompt	119	2	1	1	4	2
epic-scoped-paths	118	5	3	2	10	3
workflow-security-epic	111	1	1	1	3	1
workflow-spec-first-replace	106	2	1	1	3	2
workflow-plan-clarify-orchestration	106	2	3	3	6	1
workflow-van-brownfield	104	1	1	1	3	1
workflow-plan-multi-epic	93	1	1	1	3	2
memory-bank-paths	85	1	1	1	3	3
finish-block	83	8	6	10	24	3
workflow-refactor-epic	81	1	1	1	3	2
workflow-implement-scope-lock	75	1	1	1	3	0
workflow-analyze-core	72	2	2	2	3	1
visual-maps/idea-pipeline-mode-map	72	0	0	0	0	1
workflow-roadmap-merge	65	1	1	1	3	1
context-session-economy	56	0	0	0	0	1
test-timeout	53	0	0	0	0	0
finish-doc-router	50	0	0	0	0	4
cheatsheets/back-implement	24	1	1	1	3	1
cheatsheets/back-decompose	19	1	0	0	1	1
cheatsheets/integ-plan	17	0	0	1	1	1
cheatsheets/back-plan	17	1	0	0	1	1
cheatsheets/back-audit	17	0	0	0	0	1
2. Кандидаты на inline или удаление (0–1 ссылок из workflow-файлов ролей)
0 ссылок (не используются workflow ролями напрямую):

Файл	Строк	Примечание
workflow-idea-pipeline	205	0 прямых; 0 из shared
test-timeout	53	0 прямых; 0 из shared
visual-maps/idea-pipeline-mode-map	72	0 прямых; только 1 ref из workflow-idea-pipeline (тоже 0)
context-session-economy	56	0 прямых; только ref из workflow-idea-pipeline
finish-doc-router	50	0 прямых; ref только из finish-block и workflow-idea-pipeline
cheatsheets/back-audit	17	0 прямых; ref только из cheatsheets/back-audit (самоссылка?)
1 ссылка:

Файл	Строк	Единственный caller
cheatsheets/back-decompose	19	back_developer/workflow-decompose
cheatsheets/integ-plan	17	integration_developer/workflow-plan
cheatsheets/back-plan	17	back_developer/workflow-plan
3. Двойные ссылки внутри одного workflow-*.mdc
Workflow-файл	Shared-файл	Количество упоминаний
back_developer/workflow-analyze	workflow-analyze-core	2
back_developer/workflow-clarify	workflow-clarify-core	2
back_developer/workflow-decompose	workflow-behavior-first	3
back_developer/workflow-decompose	workflow-legacy-fallback-cleanup	2
front_developer/workflow-analyze	workflow-analyze-core	2
front_developer/workflow-decompose	workflow-behavior-first	3
front_developer/workflow-decompose	workflow-legacy-fallback-cleanup	2
front_developer/workflow-plan	workflow-plan-clarify-orchestration	2
integration_developer/workflow-analyze	workflow-analyze-core	2
integration_developer/workflow-decompose	workflow-behavior-first	3
integration_developer/workflow-decompose	workflow-legacy-fallback-cleanup	2
integration_developer/workflow-plan	workflow-plan-clarify-orchestration	2
4. Транзитивные дубли (A→B, и B тоже упомянут напрямую)
Сгруппировано по уникальным паттернам (повторяется во всех 3 ролях):

Workflow	Прямая ссылка A	Прямая ссылка B (транзитив через A)	Дублирующий shared
workflow-decompose (все 3)	workflow-behavior-first	workflow-legacy-fallback-cleanup	взаимная петля
workflow-decompose (все 3)	workflow-legacy-fallback-cleanup	workflow-behavior-first	взаимная петля
workflow-decompose (back)	cheatsheets/back-decompose	workflow-behavior-first	behavior-first лишний напрямую
workflow-decompose (back)	workflow-spec-first-replace	workflow-behavior-first	behavior-first лишний напрямую
workflow-decompose (back)	workflow-spec-first-replace	workflow-legacy-fallback-cleanup	legacy лишний напрямую
workflow-plan (все 3)	workflow-plan-clarify-orchestration	workflow-plan-outcome-prompt	outcome-prompt лишний напрямую
workflow-plan (все 3)	workflow-legacy-fallback-cleanup	workflow-plan-multi-epic	multi-epic лишний напрямую
workflow-plan (все 3)	workflow-behavior-first	workflow-legacy-fallback-cleanup	взаимная петля
workflow-plan (все 3)	workflow-spec-first-replace	workflow-behavior-first + legacy	оба лишние напрямую
workflow-plan (back)	cheatsheets/back-plan	workflow-behavior-first + outcome-prompt	оба лишние напрямую
workflow-refactor (все 3)	workflow-refactor-epic	finish-block	finish-block лишний напрямую
workflow-van (все 3)	workflow-van-brownfield	memory-bank-paths	взаимная петля
workflow-van (все 3)	memory-bank-paths	workflow-van-brownfield	взаимная петля
workflow-clarify (все 3)	workflow-plan-clarify-orchestration	workflow-clarify-core	clarify-core лишний напрямую
workflow-implement (back)	cheatsheets/back-implement	workflow-behavior-first	behavior-first лишний напрямую
workflow-implement (back)	workflow-legacy-fallback-cleanup	workflow-behavior-first	взаимная петля
integ/workflow-plan	cheatsheets/integ-plan	finish-block	finish-block лишний напрямую
5. Топ-10 самых тяжёлых файлов (строк × количество workflow-файлов-потребителей)
#	Shared-файл	Строк	Потребляющих workflow	Счёт (строк×wf)
1	workflow-legacy-fallback-cleanup	260	10	2600
2	finish-block	83	24	1992
3	workflow-behavior-first	250	7	1750
4	epic-scoped-paths	118	10	1180
5	workflow-plan-clarify-orchestration	106	6	636
6	workflow-plan-outcome-prompt	119	4	476
7	workflow-clarify-core	151	3	453
8	workflow-spec-first-replace	106	4	424
9	workflow-security-epic	111	3	333
10	workflow-van-brownfield	104	3	312
Ключевые выводы:

finish-block и workflow-legacy-fallback-cleanup — самая высокая нагрузка на Read; finish-block упоминается в 24 уникальных workflow-файлах.
workflow-behavior-first ↔ workflow-legacy-fallback-cleanup — взаимная петля: каждый ссылается на другой, и оба упомянуты напрямую в одних и тех же workflow (decompose, plan). Агент может читать пару дважды.
workflow-plan-clarify-orchestration → workflow-plan-outcome-prompt и workflow-clarify-core — оба транзитива присутствуют напрямую в нескольких workflow.
workflow-van-brownfield ↔ memory-bank-paths — взаимная петля в workflow-van всех 3 ролей.
6 файлов с 0 прямых ссылок от workflow ролей: workflow-idea-pipeline, test-timeout, visual-maps/idea-pipeline-mode-map, context-session-economy, finish-doc-router, cheatsheets/back-audit.
У меня есть все данные. Формирую структурированный отчёт.

Аудит workflow-файлов BACK role: паттерны избыточных Read
Легенда полей
W = workflow-*.mdc (основной)
L = _lean/*.mdc (gates)
C = cheatsheet/back-*.mdc
"вклеить" = файл мал и упомянут в одном месте — его контент можно слить прямо в вызывающий файл
"двойная ссылка" = один и тот же shared-файл упомянут ≥2 раз в рамках одного workflow
ANALYZE
Файлы, которые агент читает (прямые @-ссылки):

#	Файл	Строк	Источник ссылки
1	back_developer/mainrule-core.mdc	н/д	W (шапка)
2	isolation_rules/_lean/analyze.mdc	30	W (шапка Gates)
3	shared/workflow-analyze-core.mdc	н/д	W + L
4	templates/analyze/epic-analyze.yaml	н/д	W + L
Итого ссылок: 4 файла (+ 2 runtime файла памяти: activeContext.md, plan/*.md)

Число файлов (правила): 4. Строк пары W+L: 62 + 30 = 92.

Cheatsheet: нет (для ANALYZE не создан cheatsheet).

Дублирование W + L: workflow-analyze.mdc (62 стр.) полностью дублирует логику _lean/analyze.mdc (30 стр.) в части NFR-3, NFR-4, boundaries и passes. L является сжатым дублем W-секций Gates и Boundaries. Агент читает оба.

Что можно вклеить: _lean/analyze.mdc (30 строк, одна ссылка) — весь контент умещается в шапочный блок Gates внутри W.

Двойная ссылка shared: shared/workflow-analyze-core.mdc упомянут и в W строка 9, и в L строка 8 — двойная ссылка при чтении обоих файлов.

ARCHIVE
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/archive.mdc	30	W
3	shared/epic-scoped-paths.mdc	н/д	W + L
Итого: 3 файла. Строк W+L: 24 + 30 = 54.

Cheatsheet: нет.

Дублирование: W (24 стр.) и L (30 стр.) — L длиннее W. L добавляет Level delta таблицу и детализацию Abort, которых нет в W. Тем не менее W уже содержит большинство шагов L в prose-форме.

Что можно вклеить: _lean/archive.mdc (30 строк) — одна ссылка во всём корпусе, файл небольшой, сливается в W.

Двойная ссылка shared: shared/epic-scoped-paths.mdc упомянут в W строка 8 и в L строка 7 — двойная ссылка.

AUDIT
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/audit.mdc	37	W
3	shared/cheatsheets/back-audit.mdc	17	— (отдельный вызов)
Итого: 3 файла. Строк W+L+C: 67 + 37 + 17 = 121.

Cheatsheet + полный workflow рядом: ДА. back-audit.mdc (17 стр.) — компактный hot path. workflow-audit.mdc (67 стр.) — полный. Сосуществуют как "default first / fallback". Это корректный паттерн (аналог decompose/implement/plan), но агент, читающий cheatsheet + L одновременно, получает трёхкратное дублирование одного scope (scope AUDIT = current iteration contracts).

Что можно вклеить: back-audit.mdc (17 строк) — если это единственный entry point перед эскалацией в полный W, можно встроить прямо в первый шаг.

Двойная ссылка shared: нет в одном файле.

BUGFIX
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/bugfix.mdc	24	W
3	shared/epic-scoped-paths.mdc	н/д	W (шаг 1) + L (шапка)
4–10	.agents/skills/*/SKILL.md × 7	н/д	W (skills list)
Итого правил: 3 + 7 skills. Строк W+L: 18 + 24 = 42.

Cheatsheet: нет.

Дублирование W + L: W (18 стр.) — почти конспект; L (24 стр.) — полнее (Gates, Abort). Частичное дублирование описания артефактного пути и root-cause gate.

Что можно вклеить: _lean/bugfix.mdc (24 строки) — единственная ссылка, малый файл. Сливается в W.

Двойная ссылка shared: shared/epic-scoped-paths.mdc — W строка 11 (шаг 1) и L строка 10 (шапка Канон).

CLARIFY
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/clarify.mdc	29	W
3	shared/workflow-clarify-core.mdc	н/д	W (Shared core) + L
4	shared/workflow-plan-clarify-orchestration.mdc	н/д	W (PLAN orchestration) + L
5	templates/clarify.md	н/д	W + L
6	.agents/skills/grill-me/SKILL.md	н/д	W (HARD)
7	.agents/skills/brainstorming/SKILL.md	н/д	W (опционально)
Итого: 7 файлов. Строк W+L: 91 + 29 = 120.

Cheatsheet: нет.

Дублирование W + L: тройное упоминание одного набора файлов. shared/workflow-clarify-core.mdc указан в W строка 8 и в L строка 8. shared/workflow-plan-clarify-orchestration.mdc — W строка 9 и L строка 9. templates/clarify.md — W строка 10 и L строка 10.

Что можно вклеить: _lean/clarify.mdc (29 строк, одна ссылка на него из W).

Двойная ссылка shared в одном workflow:

shared/workflow-clarify-core.mdc — W + L (читаются последовательно)
shared/workflow-plan-clarify-orchestration.mdc — W + L
templates/clarify.md — W + L
Три shared-файла дублированы в паре W+L.

CREATIVE
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/creative.mdc	28	W
3	back_developer/skills-gate-situational.mdc	н/д	W (шаг 1a, 2a) + L
4	.agents/skills/brainstorming/SKILL.md	н/д	W (Core)
5	.agents/skills/architecture-patterns/SKILL.md	н/д	W (Core)
6–10	situational skills ≤5	н/д	W
Итого: 5+ файлов. Строк W+L: 75 + 28 = 103.

Cheatsheet: нет.

Дублирование W + L: skills-gate-situational.mdc упомянут в W строка 8 и в L строка 13.

Что можно вклеить: _lean/creative.mdc (28 строк) — одна прямая ссылка в W.

Двойная ссылка shared: back_developer/skills-gate-situational.mdc упомянут дважды даже внутри W (строки 8 и 25 — шапка и шаг 1 процесса).

DECOMPOSE
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/decompose.mdc	32	W
3	shared/cheatsheets/back-decompose.mdc	19	W (Default hot path, читать первым)
4	back_developer/skills-gate-situational.mdc	н/д	W
5	shared/workflow-behavior-first.mdc	н/д	W (Policy) + C
6	shared/workflow-legacy-fallback-cleanup.mdc	н/д	W (Policy) + C
7	shared/workflow-spec-first-replace.mdc	н/д	W (Policy)
8	.agents/skills/writing-plans/SKILL.md	н/д	W
9	.agents/skills/brainstorming/SKILL.md	н/д	W (условно)
Итого: 9 файлов (без skills). Строк W+L+C: 64 + 32 + 19 = 115.

Cheatsheet + полный workflow рядом: ДА. back-decompose.mdc (19 стр.) = hot path. workflow-decompose.mdc (64 стр.) = full. Паттерн корректен (cheatsheet ссылается назад на full → @.cursor/rules/back_developer/workflow-decompose.mdc). Но cheatsheet в строке 5 (workflow-behavior-first.mdc §1·§1a·§3a) и workflow в строке 10 тоже ссылаются на тот же файл — двойная ссылка.

Что можно вклеить: back-decompose.mdc (19 строк) слитком мал — его можно встроить прямо в шапку W как "Quick path" блок, устранив отдельный Read.

Двойная ссылка shared:

shared/workflow-behavior-first.mdc — W строка 10 и C строка 9, 18
shared/workflow-legacy-fallback-cleanup.mdc — W строка 10 и C (строка 18 → ссылка в footer)
IMPLEMENT
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/implement.mdc	55	W
3	shared/cheatsheets/back-implement.mdc	24	W (Default hot path)
4	shared/workflow-implement-scope-lock.mdc	н/д	W + L
5	shared/workflow-behavior-first.mdc	н/д	W (lazy) + L + C
6	shared/workflow-legacy-fallback-cleanup.mdc	н/д	W (lazy) + L + C
7	shared/finish-block.mdc	н/д	W (перед FINISH) + L
8	shared/epic-scoped-paths.mdc	н/д	L
9	rules/mainrule.mdc	н/д	W + L
10+	skills.impl из sNN	н/д	W + L
Итого: 9 файлов правил + N skills. Строк W+L+C: 44 + 55 + 24 = 123.

Cheatsheet + полный workflow рядом: ДА. Тот же паттерн. Cheatsheet back-implement.mdc (24 стр.) — hot path; W — при FAIL.

Двойная ссылка shared (критично — 4 файла):

shared/workflow-implement-scope-lock.mdc — W строка 8, L строка 7
shared/workflow-behavior-first.mdc — W строка 14 (lazy), L строки 28, 29 (wire_complete/purge), C строки 17
shared/workflow-legacy-fallback-cleanup.mdc — W строка 15, L строка 27, C строки 17
shared/finish-block.mdc — W строка 42, L строка 31, C строка 14
Это самая насыщенная команда по числу пересечений.

Что можно вклеить: back-implement.mdc (24 строки) — встроить в шапку W как Quick path block. _lean/implement.mdc (55 строк) — нельзя вклеить, он длиннее W.

PLAN
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/plan.mdc	42	W
3	shared/cheatsheets/back-plan.mdc	17	W (Default hot path)
4	shared/workflow-plan-clarify-orchestration.mdc	н/д	W + L
5	back_developer/workflow-clarify.mdc	91	W (CLARIFY Phase 0 mechanics)
6	shared/workflow-plan-multi-epic.mdc	н/д	W + L
7	shared/workflow-plan-outcome-prompt.mdc	н/д	W + L + C
8	shared/workflow-legacy-fallback-cleanup.mdc	н/д	W (по триггеру)
9	shared/workflow-spec-first-replace.mdc	н/д	W
10	shared/workflow-behavior-first.mdc	н/д	W + C
11	.agents/skills/writing-plans/SKILL.md	н/д	W
12	.agents/skills/grill-me/SKILL.md	н/д	W
13	.agents/skills/python-testing-patterns/SKILL.md	н/д	W
14–16	situational skills 1–3	н/д	W
Итого: 10 правил + skills. Строк W+L+C: 60 + 42 + 17 = 119.

Особенность PLAN: W ссылается на workflow-clarify.mdc (91 строка!) как на механику Phase 0 — то есть агент в рамках PLAN может читать ещё один полный workflow.

Cheatsheet + полный workflow рядом: ДА (3 уровня: C → W → workflow-clarify).

Двойная ссылка shared:

shared/workflow-plan-clarify-orchestration.mdc — W строка 9 и L строка 8
shared/workflow-plan-multi-epic.mdc — W строка 11 и L строка 9
shared/workflow-plan-outcome-prompt.mdc — W строка 12, L строка 7, C строка 3p
shared/workflow-behavior-first.mdc — W строка 13, C строка 11, 17
Что можно вклеить: back-plan.mdc (17 строк) и _lean/plan.mdc (42 строки) имеет смысл слить, т.к. L содержит те же gate-правила что W — но на 18 строк короче.

QA
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/qa.mdc	51	W
3	shared/epic-scoped-paths.mdc	н/д	L
4	shared/workflow-legacy-fallback-cleanup.mdc	н/д	W (brownfield) + L
5	shared/workflow-behavior-first.mdc	н/д	W (verification) + L
6–15	skills (core+situational)	н/д	W
Итого: 5 правил + skills. Строк W+L: 28 + 51 = 79.

Cheatsheet: нет (только для AUDIT, DECOMPOSE, IMPLEMENT, PLAN существуют cheatsheets).

Дублирование W + L: QA — один из редких случаев где L (51 стр.) значительно длиннее W (28 стр.). L содержит всю детальную логику (brownfield gates, behaviour smoke, situational table, abort conditions). W — краткая обёртка. По сути W избыточен: агент мог бы стартовать прямо с L.

Двойная ссылка shared:

shared/workflow-legacy-fallback-cleanup.mdc — W строка 28, L строка 20a
shared/workflow-behavior-first.mdc — W строка 28, L строки 21b, 22
REFACTOR
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/refactor.mdc	27	W
3	shared/workflow-refactor-epic.mdc	н/д	W + L
4–10	.agents/skills/*/SKILL.md × 7	н/д	W
Итого: 3 правила + 7 skills. Строк W+L: 32 + 27 = 59.

Cheatsheet: нет.

Двойная ссылка shared: shared/workflow-refactor-epic.mdc — W строка 8 и L строка 7.

Что можно вклеить: _lean/refactor.mdc (27 строк) — слить в W. При этом W уже содержит практически полный процесс.

REFLECT
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/reflect.mdc	29	W
3	shared/finish-block.mdc	н/д	W (шаг 7)
Итого: 3 файла. Строк W+L: 29 + 29 = 58 (симметрия).

Cheatsheet: нет.

Дублирование W + L: оба файла 29 строк. W и L содержат практически одинаковый набор: секции артефакта, Orchestration signals, Promote candidates. L добавляет Level delta таблицу.

Что можно вклеить: _lean/reflect.mdc (29 строк) — слить в W, убрав дублирование по секциям.

ROADMAP-MERGE
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/roadmap-merge.mdc	17	W
3	shared/workflow-roadmap-merge.mdc	н/д	W + L
Итого: 3 файла. Строк W+L: 23 + 17 = 40.

Cheatsheet: нет.

Самая лёгкая команда. W и L вместе — 40 строк.

Что можно вклеить: _lean/roadmap-merge.mdc (17 строк) — слить в W. shared/workflow-roadmap-merge.mdc упомянут в обоих (W строка 8, L строка 8) — двойная ссылка.

SECURITY
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/security.mdc	43	W
3	shared/workflow-security-epic.mdc	н/д	W + L
4–16	.agents/skills/*/SKILL.md × 13	н/д	W
Итого: 3 правила + 13 skills. Строк W+L: 70 + 43 = 113.

Cheatsheet: нет.

Самая длинная команда по skills-списку — 13 skills перечислены в W. Однако это список "доступных"; какие реально читаются — зависит от submode (PLAN/DECOMPOSE/EXECUTE).

Двойная ссылка shared: shared/workflow-security-epic.mdc — W строка 8 и L строка 7.

Что можно вклеить: _lean/security.mdc (43 строки) — не стоит, он длиннее многих W.

TASK
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/task.mdc	20	W
3	shared/finish-block.mdc	н/д	W (шаг 12)
4–8	.agents/skills/*/SKILL.md × Core(4) + situational	н/д	W
Итого: 3 правила + N skills. Строк W+L: 24 + 20 = 44.

Cheatsheet: нет.

Минимальная нагрузка. L (20 строк) — самый короткий lean-файл.

Что можно вклеить: _lean/task.mdc (20 строк) — однозначно сливается в W.

VAN
Файлы, которые агент читает:

#	Файл	Строк	Источник
1	back_developer/mainrule-core.mdc	н/д	W
2	isolation_rules/_lean/van.mdc	34	W
3	shared/workflow-van-brownfield.mdc	н/д	W + L
4	shared/memory-bank-paths.mdc	н/д	W + L
Итого: 4 файла. Строк W+L: 27 + 34 = 61.

Cheatsheet: нет.

Дублирование W + L: L (34 строки) длиннее W (27 строк). L содержит Complexity таблицу и Abort, W — процесс.

Двойная ссылка shared:

shared/workflow-van-brownfield.mdc — W строка 8 и L строка 9
shared/memory-bank-paths.mdc — W строка 9 и L строка 10
Сводная таблица
Команда	W строк	L строк	C строк	Итого строк	Cheatsheet	L можно вклеить	Двойных shared
ANALYZE	62	30	—	92	нет	да (30)	1
ARCHIVE	24	30	—	54	нет	да (30)	1
AUDIT	67	37	17	121	да	да (37)	0
BUGFIX	18	24	—	42	нет	да (24)	1
CLARIFY	91	29	—	120	нет	да (29)	3
CREATIVE	75	28	—	103	нет	да (28)	1
DECOMPOSE	64	32	19	115	да	нет (32 + C=19)	2
IMPLEMENT	44	55	24	123	да	нет (L=55 > W)	4
PLAN	60	42	17	119	да	нет (L=42)	4
QA	28	51	—	79	нет	нет (L=51 > W)	2
REFACTOR	32	27	—	59	нет	да (27)	1
REFLECT	29	29	—	58	нет	да (29)	0
ROADMAP-MERGE	23	17	—	40	нет	да (17)	1
SECURITY	70	43	—	113	нет	нет (L=43)	1
TASK	24	20	—	44	нет	да (20)	0
VAN	27	34	—	61	нет	нет (L=34 > W)	2
Ключевые выводы и паттерны экономии Read
1. Паттерн "W+L читаются вместе, но L < W" — кандидаты на слияние L→W:

Для 9 команд (ANALYZE, ARCHIVE, BUGFIX, CLARIFY, CREATIVE, REFACTOR, REFLECT, ROADMAP-MERGE, TASK) L-файл меньше 30 строк и упомянут только из W. Слияние устраняет 1 Read на каждую сессию.

2. Паттерн "двойная ссылка на shared" — встречается в 13 из 16 команд:

Наиболее частые жертвы:

shared/workflow-behavior-first.mdc — упомянут в 6 командах (DECOMPOSE, IMPLEMENT, PLAN, QA, AUDIT, CLARIFY)
shared/epic-scoped-paths.mdc — в 5 командах (ARCHIVE, BUGFIX, QA, IMPLEMENT, CREATIVE)
shared/finish-block.mdc — в 3 командах (IMPLEMENT, REFLECT, TASK) через и W и L
3. Паттерн "cheatsheet + W + L = тройная нагрузка":

Только 4 команды имеют cheatsheet (AUDIT, DECOMPOSE, IMPLEMENT, PLAN). В этих командах агент потенциально читает 3 слоя: C (hot path) + L (gates) + W (full, при FAIL). Каждый слой дублирует базовую логику scope/artifact path в разной степени. Для IMPLEMENT это особенно выражено: L (55 стр.) длиннее W (44 стр.) и содержит 4 ссылки на shared файлы.

4. Инвертированный паттерн "L длиннее W":

QA (L=51 > W=28), IMPLEMENT (L=55 > W=44), VAN (L=34 > W=27), ARCHIVE (L=30 > W=24). В этих случаях чтение W малоценно — агент получает больше информации из L, чем из W. Для QA и IMPLEMENT W фактически является thin-wrapper над L.

Что теряется при удалении _lean/ и вклейке в W:

Ничего критичного — каждый _lean файл является подмножеством или парафразом W
Level delta таблица (есть только в _lean) — добавляется в W как секция ## Gates (quick ref)
Abort conditions (иногда только в _lean) — добавляются в W
Вывод: _lean/ слой можно полностью упразднить без потери контента при одном условии — перенести Gates checklist + Level delta + Abort в конец каждого W.

mainrule-core.mdc — можно ли вклеить в каждый W?
34 строки × 15 команд × 3 роли = 1530 строк дублирования в репо.
Но для агента это 1 Read на сессию (он читается один раз в начале).

Вывод: вклейка mainrule-core в каждый W устраняет 1 Read, но раздувает файлы на 34 строки каждый. Лучше альтернатива: вклеить в _lean (которые уже предложены к слиянию с W) — тогда и mainrule-core и _lean исчезают в одном W-файле.

Суть находок (коротко):

Три структурных паттерна дают 80% потерь:

1. W + L — два файла вместо одного (самый большой ROI)
Каждая команда читает workflow-<mode>.mdc + _lean/<mode>.mdc. L — это gates-checklist, который является подмножеством W. Слияние L → в конец W убирает 1 Read на каждую сессию для всех 16 команд × 3 ролей.

2. Cheatsheet + W + L = три слоя про одно
DECOMPOSE, IMPLEMENT, PLAN, AUDIT читают 3 файла об одном режиме. После слияния — 1 файл с секциями ## Hot path / ## Full workflow / ## Gates.

3. Двойные ссылки на один shared внутри W
workflow-behavior-first упоминается 3 раза в workflow-decompose. workflow-analyze-core — 2 раза в workflow-analyze. Агент получает сигнал читать дважды.

Итог если применить P0+P1+P2: простые команды (BUGFIX, REFLECT, TASK) — с 3 до 1 Read. Сложные (DECOMPOSE, PLAN) — с 8–10 до 4–5 Read.

Аудит паттерна mainrule-core + _lean во всех трёх ролях
1. mainrule-core.mdc — строки и контент
Роль	Строк
back_developer	60
front_developer	34
integration_developer	53
Повторяющийся контент между ролями:

Блок ## MEMORY BANK — структура одинаковая (activeContext → load_now first, Session start: context-session-economy §3), отличаются только пути memory-bank/back|front|integration/.
## ПЕРЕХОДЫ: у FRONT и INTEG почти идентичные две строки: Next-mode: memory-bank/activeContext.md + decompose index + Runner: ./loop/loop.sh. BACK развёрнут в полный flowchart.
## ФОРМАТ: OK BACK|FRONT|INTEG <РЕЖИМ> - [действие] — идентичная структура.
Блок ## pytest runner (HARD — hub exception) есть и в BACK (строки 15–26, полный), и в INTEG (строки 17–24, сжатый вариант того же). FRONT вместо него ссылается на test-timeout.mdc одной строкой.
Фраза FORBIDDEN Handoff: «manual smoke only» без scenario path — присутствует и в FRONT и INTEG почти дословно.
Уникальный контент:

BACK только: ## УРОВНИ (таблица L1–L4 с <1ч/<4ч/<2д/>2д); полная цепочка переходов VAN→PLAN→DECOMPOSE→ANALYZE→CREATIVE?→IMPLEMENT*→AUDIT→QA→REPLAN→FINAL REVIEW→DONE→ARCHIVE; правила promote DECOMPOSE→IMPLEMENT (ANALYZE artifact critical_count=0); Post-QA: I1/I2→REPLAN; I3→FINAL.
FRONT только: ## DESIGN STACK (visible UI) — канон decompose visible_ui + Design skills; правило visible_ui: no / pure lib — skip; Vitest/RTL/Playwright — только parent.
INTEG только: ## ELEMENT-FIRST (один UI-элемент за сессию); ## QUERY BUILDER (ссылка на query-builder/SKILL.md); ## КОНТРАКТ §Contract в decompose-*/eNN-*.yaml; ## BACK / FRONT в одном eNN (фазы A→F); GAP fanout ссылка в переходах.
Итого повторяющегося: ~10–12 строк из каждого файла (MEMORY BANK структура + ФОРМАТ + отчасти pytest runner). Уникального: BACK ~40 строк, FRONT ~18 строк, INTEG ~35 строк.

2. isolation_rules/_lean/ — полный аудит файлов
Размеры по ролям:

Роль	Файлов	Строк всего
back_developer	18	578
front_developer	15	477
integration_developer	18 (включая gap.mdc + gap-close.mdc)	503
Размеры ключевых файлов:

Файл	back	front	integ
implement.mdc	55	47	40
plan.mdc	42	35	30
decompose.mdc	32	48	38
qa.mdc	51	23	24
security.mdc	43	43	43
analyze.mdc	30	31	31
van.mdc	34	34	33
bugfix.mdc	24	21	20
audit.mdc	37	39	40
reconcile.mdc	19	—	—
replan.mdc	31	—	—
task.mdc	20	25	17
roadmap-merge.mdc	17	17	17
gap.mdc	—	—	34
gap-close.mdc	—	—	29
Контент _lean файлов — это только Gates-checklist или есть уникальный контент?

_Lean файлы — это НЕ просто Gates-checklist. Каждый файл содержит:

Заголовок артефакта — путь к memory-bank артефакту + канон-ссылка на шаблон. Этого нет в полном workflow, там только процесс.

Сжатый вариант Gates — workflow содержит развёрнутую прозу с примерами; _lean — только машиночитаемые условия PASS/FAIL. _lean/implement.mdc (55 строк) содержит гейты 1–8a + таблицу Level delta + Abort list. Workflow-implement.mdc (44 строки) — это инструкция процесса (как делать), _lean — это контрольный чеклист (что проверять).

Abort-блок — в _lean есть явный ## Abort с конкретными FAIL-условиями. В workflow-*.mdc abort условия рассыпаны по тексту.

Уникальные gate-специфичные правила, которых нет в workflow:

implement.mdc: gate 5a sunset_scope (HARD) — детальная логика spawn @sunset-inventory; gate 1a plan_parity_scan; plan_jumps формула L′=L×2.
plan.mdc (back): gates 8–10 (Eng review spine, QA consumes draft, Review readiness) — их нет в workflow-plan.mdc в виде самостоятельных numbered gates.
qa.mdc (back): таблица Situational с 6 тригерами и скиллами.
audit.mdc: gate 6 FINISH: PASS → BACK QA; FAIL → BACK BUGFIX — это уникальный маршрутинг.
@-ссылки: есть ли дублирование с workflow?

Да, частичное. Пример для _lean/implement.mdc vs workflow-implement.mdc:

Общие: @.cursor/rules/mainrule.mdc, @.cursor/rules/shared/workflow-implement-scope-lock.mdc, @verify, @verify-implement, @explorer.
Только в _lean: @.cursor/rules/shared/epic-scoped-paths.mdc, @.cursor/rules/shared/finish-block.mdc, @sunset-inventory, @explorer (в другом контексте).
Только в workflow: @.cursor/rules/back_developer/mainrule-core.mdc, @.cursor/rules/back_developer/isolation_rules/_lean/implement.mdc, @.cursor/rules/shared/cheatsheets/back-implement.mdc, @.cursor/rules/shared/workflow-behavior-first.mdc, @.cursor/rules/shared/workflow-legacy-fallback-cleanup.mdc.
Дублирование moderate: ~3–4 @-ссылки из ~8–12 в _lean перекрываются с workflow. Дублирование не критическое — _lean ссылается на канон артефакта, workflow ссылается на cheatsheet и policy файлы.

Файлы, практически идентичные между ролями:

roadmap-merge.mdc: BACK = FRONT = INTEG (diff exit 0 для всех пар). 17 строк, полный дубль.
security.mdc: отличается ОДНОЙ строкой (приоритетная матрица: BACK — auth/SQL/deps; FRONT — XSS/tokens/CSP/bundle/deps; INTEG — wire×authz×IDOR×contract). 43 строки, дельта 1 строка на роль.
van.mdc: BACK и FRONT различаются на ~5 строк (brownfield refresh специфика: frontend.md vs architecture/). BACK и INTEG идентичны (exit 0).
archive.mdc: FRONT отличается от BACK в ~4 строках (отсутствие creative/.md rewrite + иной abort).
reflect.mdc: BACK = FRONT = INTEG (практически).
3. Можно ли убрать _lean/ слой и вклеить gates в конец workflow-*.mdc?
Технически возможно, но потеряется следующее:

Режим быстрой загрузки. Workflow-*.mdc сейчас читается только при FAIL или неясности (hot path идёт через cheatsheet). _lean загружается всегда на старте (Load: cheatsheet + этот файл + scope-lock на старте). Если вклеить gates в конец workflow, агент будет читать весь workflow (44–64 строки процесса + 30–55 строк gates) вместо только gates (30–55 строк). README.md _lean/: Gates-only. Процесс — workflow-*.mdc.

Разделение контрактов. workflow-*.mdc описывает КАК делать (процесс, скиллы, порядок шагов); _lean описывает ЧТО проверять (pass/fail условия). Смешивание усложняет обслуживание: при изменении гейта придётся редактировать более крупный файл.

Экономия токенов. _lean не грузит: Full workflow / индекс роли / token-economy-core. Если вклеить, workflow станет длиннее и будет загружаться целиком в контекст при каждом вызове гейта.

Инструкция isolation_rules_load.md ссылается на _lean как на самостоятельный слой — потребуется обновление всех мест, ссылающихся на путь isolation_rules/_lean/<mode>.mdc.

Что НЕ потеряется: функциональность гейтов, Abort условия, маршрутинг — всё это можно технически перенести.

Вывод по вопросу 3: Убрать _lean/ как слой можно только если одновременно переработать hot-path логику (сейчас: cheatsheet → [gates как отдельный файл] → workflow при FAIL). Простое «вклеивание в конец workflow» приведёт к загрузке лишних ~30–55 строк процессной прозы каждый раз, когда нужна только gate-проверка. Экономия на числе файлов будет съедена увеличением размера каждого загружаемого workflow.

4. Можно ли вклеить mainrule-core в каждый workflow вместо отдельного Read?
Оценка overhead:

mainrule-core размеры: BACK 60 строк, FRONT 34 строки, INTEG 53 строки.

Workflow файлов: BACK 19 (из них 18 ссылаются на mainrule-core), FRONT 16, INTEG 18.

Если вклеить mainrule-core в каждый workflow:

Роль	Файлов × строк	Суммарный overhead
BACK	18 × 60	+1 080 строк дублей
FRONT	16 × 34	+544 строки дублей
INTEG	18 × 53	+954 строки дублей
Итого		+2 578 строк
Сейчас mainrule-core читается ОДИН раз на сессию через @-ссылку в шапке workflow. Это ~60/34/53 строк однократно. При вклеивании каждый вызов любого workflow загрузит полную копию mainrule-core в контекст.

Практическая проблема: если нужно изменить правило TDD или pytest runner, сейчас редактируется 1 файл. После вклеивания — 18 файлов в BACK, 16 во FRONT, 18 в INTEG = 52 файла.

Единственный аргумент за: сейчас каждый workflow требует 2 Read операции (mainrule-core + сам workflow). После вклеивания — 1 Read. Экономия 1 Read-операции на сессию.

Вывод по вопросу 4: Вклеивать нельзя. Один сэкономленный Read не окупает +2 578 строк дублирования и превращение 1 точки правки в 52. Если цель — убрать двойной Read, правильный путь — вынести общую часть mainrule-core (MEMORY BANK структура, ФОРМАТ, pytest runner) в shared файл и сократить role-специфичные mainrule-core до 15–20 строк чистого уникального контента на роль.

Резюме находок:

/home/aero/PyProject/dev-hub/.cursor/rules/back_developer/mainrule-core.mdc — 60 строк, ~40 уникальных
/home/aero/PyProject/dev-hub/.cursor/rules/front_developer/mainrule-core.mdc — 34 строки, ~18 уникальных
/home/aero/PyProject/dev-hub/.cursor/rules/integration_developer/mainrule-core.mdc — 53 строки, ~35 уникальных
roadmap-merge.mdc в _lean — полный тройной дубль (17 строк × 3), кандидат в shared/
security.mdc в _lean — 43 строки × 3, дельта 1 строка, кандидат для шаблонизации
van.mdc в _lean — BACK=INTEG полный дубль (34 строки), FRONT отличается на 5 строк
_lean слой выполняет функцию отличную от workflow: gates-as-contract vs process-as-instructions; слияние технически ломает экономику токенов