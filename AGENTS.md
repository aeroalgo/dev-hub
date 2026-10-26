# dev-hub

## Runtime entrypoint

Используй только entrypoint текущего runtime:

- Claude Code → `CLAUDE.md`
- Codex → `AGENTS.md`
- DSH → `AGENTS.md` with native `read`/`write`/`edit` tools

Не читай другой runtime entrypoint.

## HARD READ RULE

До анализа, изменений и основной работы:

- **IMPLEMENT / TASK / BUGFIX / REFACTOR:** прочитай
  `.cursor/rules/shared/_lean/implement-bootstrap.mdc` и следуй его Read order
  (Gates → scope-lock → role `## Hot path` → shard). **Не** грузи
  `mainrule.mdc` monolith на старте code-phase.
- **PLAN / DECOMPOSE / VAN / прочие:** entrypoint → `.cursor/rules/mainrule.mdc`
  → выбранная role/mode chain с Gates и `@`-ссылками.

**EXCEPT Policy lazy:** не читай тела файлов из блока/строки `Policy lazy`
на старте только из-за `@` — только по trigger (см. `mainrule.mdc` §Full linked
chain / implement-bootstrap). На **DECOMPOSE** не читай тела Core/situational/Design
SKILL.md — только copy paths в step (`shared/_lean/decompose-skills-load.mdc`).

## Workflow router

По таблице router выбери текущую команду, роль и режим. Для code-phase — bootstrap;
иначе — role/mode chain и Gates.

Не загружай workflow или skills заранее и не выбирай другую роль или режим.
Пути и имена файлов определяются каноническими workflow, index и skills.

## Workflow-owned skills

Единственный skill-root этого workflow — локальный `.agents/skills/` репозитория
(в dev-hub он указывает на `harness/skills/`). Автоматический skills-каталог
Codex отключён в `.codex/config.toml`, поэтому его полный список не является
частью стартового prompt.

Загружай только конкретные локальные `SKILL.md`, явно указанные выбранной
role/mode chain или текущим shard (`skills.impl`, `skills.design`,
`skills.design_skills`, audit skills). Если workflow или shard не назвал
skill-путь, не загружай skills и не угадывай соседние. Явный запрос пользователя
или runtime на конкретный skill имеет приоритет.

Для DSH ссылки `@file` — это навигация, а не готовый system prompt: прочитай
entrypoint, выбери текущую фазу, затем последовательно прочитай только файлы
выбранной цепочки и явно перечисленные `SKILL.md`.

## Session context

Для role command используй `memory-bank/activeContext.md` и только текущие
пути из `load_now`. Не подменяй текущий shard другим epic или режимом.
Write `activeContext` — `.cursor/rules/token-economy-stub.mdc` §0.7.

## Context ledger and budget enforcement

- Context ledger: durable metadata tracking для Read/Edit решений (allow, cached-ref, duplicate deny, split, fail.closed).
- Read semantics: duplicate Read неизменённого диапазона запрещён; при изменении файла (hash mismatch) перечитывается только новый диапазон.
- Plan jump: IMPLEMENT/TASK/BUGFIX используют ограниченные `plan_jumps`, чтение whole plan запрещено.
- Search allowlist: поиск ограничен файлами шага (`files:`); расширенный поиск требует graphify receipt.
- Derived identity: root и subagent соблюдают единый контракт ledger и derived_identity без provider drift.

## Общие правила

- Отвечай пользователю на русском языке.
- В конце ответа указывай название модели ИИ.
- Исправляй причину ошибки, не скрывай её fallback-логикой.
- Коммиты и PR выполняй только по явному запросу.
- Комментарии в коде добавляй только по запросу.

## Frappe / ERPNext / CRM — стиль кода и тестов (HARD)

Канон для кода в `frappe/`, `erpnext/`, `crm/`, `hrms/` (не для Python-хаба `bin/pytest`).

### Стиль программирования

- **Пишем в стиле уже существующего кода этого репо**, не «как в FastAPI/Django REST с нуля».
- API = `@frappe.whitelist()` + `return dict` / Document API; HTTP-обёртка — Frappe (`/api/method/...`, `/api/resource/...`).
- Модели данных = DocType (`*.json` + `*.py` Document), не отдельные Pydantic/SQLAlchemy-слои «сбоку», если as-built так не устроен.
- Перед новым модулем — найти соседний образец в том же app (page / whitelist / test) и копировать паттерны: импорты, `frappe.get_all`, права `has_permission`, именование, структура ответа.
- **FORBIDDEN:** параллельный стек (свой FastAPI, свой TestClient, свой OpenAPI) рядом с Frappe для той же фичи; silent fallback; «временный» код без теста.
- **Новый CRM API и архитектура бэкенда (HARD):**
  - Архитектурный канон слоёв: `.cursor/rules/crm-architecture.mdc` (Adapter, Service, Repository, Schema).
  - API-контракт: `.cursor/rules/crm-api-contract.mdc` — явный `methods=[...]`, Pydantic-валидация входа, обязательный Out-контракт, тонкий adapter (без толстой бизнес-логики и SQL прямо в методе), ошибки через `frappe.throw` / typed exceptions (не success-body при ошибке).
  - **FORBIDDEN:** FastAPI / Starlette / Django REST app в CRM; толстые whitelist без `methods=[...]`.
  - Scope foundation_only: архитектурные каркасы и правила задают канон и не обещают сразу готовый продуктовый endpoint. Не размазывать этот контракт на правки upstream `frappe/` / `erpnext/` / `hrms/`.

### Стиль тестов

- Тесты пишем **в стиле, который уже есть в apps**, не изобретаем другой runner «для удобства».
- Образцы:
  - HTTP API ядра: `frappe/frappe/tests/test_api.py` (`FrappeAPITestCase`)
  - App / DocType / whitelist: `FrappeTestCase` рядом с кодом (`erpnext/**/test_*.py`, `crm/crm/tests/test_*.py`)
- Для нового `@frappe.whitelist()` в том же эпике/сессии IMPLEMENT:
  1. тест на контракт ответа (ключи / типы / ветки) — минимум;
  2. при user-facing HTTP — по возможности вызов через `FrappeAPITestCase` / `self.get(self.method("app.module.fn"))`, как в `test_api.py`;
  3. прогон через **bench** (обычно Docker backend):  
     `bench --site <site> run-tests --app <app> --module <dotted.module>`  
     Smoke `bench execute` **не** заменяет тест.
- **FAIL / не done:** prod whitelist или Desk-wire без теста в стиле app; только ручной клик / `execute` без `test_*.py`.
- Hub `bin/pytest` — только self-test хаба; **не** подменять им suite Frappe/ERPNext/CRM.

### Где гонять

- Runtime apps: контейнер backend / `frappe-bench` + `bench run-tests`.
- CRM UI: Vitest / Playwright (см. § Root classification & Testing и `crm/AGENTS.md`).
- Не считать «зелёным» только build/migrate без прогона релевантных `test_*.py`.

## EVAL (оценка ниши)

Команды `EVAL FRAME|SEARCH|PRICE|GATE|…` — не BACK. Индекс: `.cursor/rules/eval/mainrule.mdc`.  
Карта: `memory-bank/product/eval-pipeline.md`. Артефакты: `memory-bank/niche/<slug>/`.

## Root classification & Testing

- Hub (dev-hub self-test) / **BACK**: Python tests — `bin/pytest …` (300s встроен) или `timeout -k 10s 300s .venv/bin/pytest …`.
- **BACK QA live_smoke (HARD):** `timeout -k 10s 300s bash scripts/live_smoke.sh` — живой uvicorn+HTTP; ASGI e2e/моки не считаются. Missing deps → установить в `.venv` (`pip install -e ".[dev]"`) и повторить (канон: `role-core-contract` §Environment bootstrap · `_lean/qa.mdc` §2c).
- **FRONT** (IMPLEMENT/TASK/QA): Vitest + Playwright. В этом репо: `timeout -k 10s 300s npm --prefix crm/frontend exec vitest …` и `timeout -k 10s 300s bash -lc 'cd crm && npx playwright test …'`. **FORBIDDEN:** `bin/pytest` / backend pytest как FRONT suite.
- **CRM Playwright runtime:** `BASE_URL=http://erp.localhost:8000`. Compose держит `sleep infinity` — нужен отдельно `bench start` в контейнере. Editable `crm/`+`frappe/`+`design-system/` ≠ `frappe-bench/apps/*` (копии get-app). `npx playwright test` → `e2e/global-setup.ts` → `scripts/e2e-preflight.sh` (sync hooks/frontend/design-system/**и** Desk SCSS wires `desktop.scss`/`desk.bundle.scss` → CRM `yarn build` → **`bench build --app frappe`** → clear-cache → **HTTP 200** tokens.css + desk.bundle содержит `--ds-desk-rail-width` если есть shell). Clear-cache alone ≠ Desk CSS update. Канон: `crm/AGENTS.md` § E2E.
- **CRM AUDIT finish:** `verdict: FAIL` / `converged: false` → **обязан** `@gate-repair` (BLOCKERS|path|fix + ALLOW WRITE + VERIFY) → повторный AUDIT. **Нельзя** закончить сессию «просто отчётом» — loop даст `finish_not_committed` / `retry_exhausted`. `mb-finish` при `converged: false` отклоняет FINISH. **FORBIDDEN** выдуманный `parent-driven-audit`. Negative `rg` без hit = exit 1 = PASS. Канон: `workflow-audit.mdc` + `spawn-hard.md`.
- **CRM QA finish:** `verify-qa` FAIL + `qa-*.yaml` (`verdict: fail`) + open `bugfix-queue.yaml` → **обязан** `loop.py finish --step QA` → BUGFIX. FAIL ≠ запрет finish (это не IMPLEMENT). Без finish → `finish_not_committed` / retry QA. Канон: `workflow-qa.mdc` + `_lean/qa.mdc`.
- **CRM BUGFIX sessions:** один open item за сессию — ок; выход без finish при ещё open → loop `PROGRESS_CONTINUE` (не halt). `verify-bugfix` + `finish --step BUGFIX` только когда все items `done` и `verification.status=pass`. Канон: `_lean/bugfix.mdc`.
- **DECOMPOSE YAML:** в `verify:`/`command:` double-quoted нельзя писать `\.` (YAML unknown escape → `verdict hook error` → `finish_not_committed`). Используй single quotes или block `|`. Один step в index ↔ один файл в `yaml/steps/`; orphan yaml запрещены. Нельзя объявлять DECOMPOSE done без accepted `verify-decompose` PASS + `loop.py finish`.
- **CRM purge `rg`:** только bounded theme/instruction paths; **FORBIDDEN** `sync.*disabled` по всему `frappe/` (ложный hit в jquery). Канон: `crm/AGENTS.md` § Purge.
- Managed projects: верификация через stack profile `capability_checks` и typed execution evidence; без generic fallback к raw pytest. Role surface сохраняется (front checks ≠ backend suite).
