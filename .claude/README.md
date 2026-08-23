# Claude Code setup ()

Зеркало Cursor workflow. **Single source of truth:** `.cursor/rules/` + `memory-bank/`.

## Быстрый старт

```bash
cd /home/aero/PyProject/
claude
/status
```

Команды в чате = slash-команды (1:1). Примеры:

```
BACK PLAN          →  /back-plan
FRONT CREATIVE     →  /front-creative
PM PLAN            →  /pm-plan
IDEA PIPELINE      →  /idea-pipeline
```

## Все slash-команды (81)

### BACK (15)

| Slash | Chat |
|-------|------|
| `/back-van` | BACK VAN |
| `/back-plan` | BACK PLAN |
| `/back-roadmap-merge` | BACK ROADMAP MERGE |
| `/back-decompose` | BACK DECOMPOSE |
| `/back-creative` | BACK CREATIVE |
| `/back-implement` | BACK IMPLEMENT |
| `/back-task` | BACK TASK |
| `/back-bugfix` | BACK BUGFIX |
| `/back-refactor` | BACK REFACTOR |
| `/back-qa` | BACK QA |
| `/back-security` | BACK SECURITY |
| `/back-security-plan` | BACK SECURITY PLAN |
| `/back-security-decompose` | BACK SECURITY DECOMPOSE |
| `/back-reflect` | BACK REFLECT |
| `/back-archive` | BACK ARCHIVE NOW |

### FRONT (15)

| Slash | Chat |
|-------|------|
| `/front-van` | FRONT VAN |
| `/front-plan` | FRONT PLAN |
| `/front-roadmap-merge` | FRONT ROADMAP MERGE |
| `/front-decompose` | FRONT DECOMPOSE |
| `/front-creative` | FRONT CREATIVE |
| `/front-implement` | FRONT IMPLEMENT |
| `/front-task` | FRONT TASK |
| `/front-bugfix` | FRONT BUGFIX |
| `/front-refactor` | FRONT REFACTOR |
| `/front-qa` | FRONT QA |
| `/front-security` | FRONT SECURITY |
| `/front-security-plan` | FRONT SECURITY PLAN |
| `/front-security-decompose` | FRONT SECURITY DECOMPOSE |
| `/front-reflect` | FRONT REFLECT |
| `/front-archive` | FRONT ARCHIVE NOW |

### INTEG (3+)

| Slash | Chat |
|-------|------|
| `/integ-van` | INTEG VAN (brownfield → полная `architecture/`) |
| `/integ-gap` | INTEG GAP (алиас INTEGRATION GAP; rewrite §Gaps → link) |
| `/integ-gap-close` | INTEG GAP CLOSE (follow links + rewire) |
| `/integ-plan` | INTEG PLAN (SUSPENSION GUARD — plan unlimited) |
| `/integ-decompose` | INTEG DECOMPOSE (batch: все eNN за один проход) |
| `/integ-security` | INTEG SECURITY |
| `/integ-security-plan` | INTEG SECURITY PLAN |
| `/integ-security-decompose` | INTEG SECURITY DECOMPOSE |
| `/loop-run` | **LOOP** — шпаргалка: запуск `./loop/loop.sh` **снаружи** сессии |
| `/epic-run` | alias → `/loop-run` (без `--track`) |
| `/program-run` | alias → `/loop-run` (DAG/`GAP_FANOUT` через актуальные флаги) |

Остальные INTEG-команды — через chat (`INTEG IMPLEMENT`, …); slash — по мере добавления в `.claude/commands/`.

### IDEA PIPELINE (4)

| Slash | Chat |
|-------|------|
| `/idea-pipeline` | IDEA PIPELINE |
| `/idea-pipeline-continue` | IDEA PIPELINE CONTINUE |
| `/idea-pipeline-finish` | IDEA PIPELINE FINISH |
| `/idea-pipeline-status` | IDEA PIPELINE STATUS |

### PM (12) — архив `_archive/cursor-rules/project_manager/`

`/pm-init` `/pm-discover` `/pm-discover-market` `/pm-plan` `/pm-roadmap` `/pm-backlog` `/pm-sprint-plan` `/pm-jira` `/pm-status` `/pm-session` `/pm-retro` `/pm-archive`

### TL (6) — архив `team_lead/`

`/tl-standup` `/tl-sprint` `/tl-delivery` `/tl-blockers` `/tl-capacity` `/tl-sync-dev`

### CONTENT (8) — архив `content_growth/`

`/content-init` `/content-plan` `/content-write` `/content-seo` `/content-audit` `/content-launch` `/content-optimize` `/content-interview`

### MARKETING (8) — архив `marketing_growth/`

`/marketing-plan` `/marketing-ads` `/marketing-email` `/marketing-monetize` `/marketing-retain` `/marketing-social` `/marketing-pr` `/marketing-revops`

### SEO (9) — архив `seo_ops/`

`/seo-tech` `/seo-local` `/seo-links` `/seo-geo` `/seo-content-ops` `/seo-ecommerce` `/seo-data` `/seo-competitors` `/seo-aso`

## Что куда

| Файл | Роль |
|------|------|
| `CLAUDE.md` | Layer 0 + imports token-economy + mainrule |
| `.claude/skills/role-command/` | Цепочка всех role commands (Step 0 = graphify для code modes) |
| `.claude/commands/*.md` | Slash-команды (по одной на режим) |
| `.claude/agents/*.md` | Custom subagents: `reviewer`, `verify`, `explorer` |
| `.claude/rules/` | Path-scoped доп. правила |
| `.claude/rules/language.md` | **Always-on** — русский язык чата (Layer 0) |
| `.claude/rules/front-tests-parent-only.md` | **Always-on** — frontend-тесты только в parent, never subagent |
| `.claude/settings.json` | hooks + `permissions` (Edit/Read scoped to repo; loop `dontAsk`) |
| `.claude/settings.local.json.example` | локальный overlay; `cp` → `settings.local.json` (gitignored) |
| `~/.claude/rules/02-front-tests-parent-only.md` | **Глобально** — frontend-тесты только parent |
| `.venv/bin/graphify` | CLI графа (не в PATH) — из **корня репо**: `query` / `path` / `explain` / `update .` → только `<repo>/graphify-out/` |

## Subagents

**Обязательные** gate’ы (packed prompt). Прочие Agent — свободно.

| Agent | Когда | Как вызвать |
|-------|-------|-------------|
| `explorer` | codebase search в IMPLEMENT/REFACTOR/BUGFIX/TASK (обязателен) | `@explorer` / Agent; Цель · GRAPHIFY · ALLOW |
| `verify` | Pre-FINISH при code_changed (обязателен) | `@verify` / Agent; AC+ · AC− · §0.11 · VERIFY · ALLOW |
| `reviewer` | BACK QA после suite (обязателен) | `@reviewer` / Agent; Suite · AC+ · AC− · §0.11 · ALLOW |

Контракт: `.claude/instructions/spawn-hard.md` + `.claude/agents/*.md`.  
Первый раз после создания каталога `agents/` — **restart** Claude Code, иначе watcher не подхватит.

### Add-agent recipe

Чтобы добавить managed overlay без изменений hook-кода:

1. Создайте `.claude/agents/researcher.md` с frontmatter `name`, `description`, tools и `overlay`.
2. В `overlay` укажите `managed: true`, режим `optional|search|gate`, `requires_model` и defaults `default_loop`/`default_chat`.
3. Добавьте `PROJECT_AGENT_RESEARCHER_MODEL=sonnet` в `.claude/project.env`.
4. При необходимости задайте независимые selectors `PROJECT_AGENT_RESEARCHER_MODEL_CHAT=1` и `PROJECT_AGENT_RESEARCHER_MODEL_LOOP=0` (отсутствие сохраняет default loop=1/chat=0).
5. Выполните `./loop/loop.sh --status` и проверьте policy/diagnostics для нового агента.
6. Не редактируйте `.claude/hooks/_lib.py` или `.claude/settings.json`: registry автоматически обнаруживает `.claude/agents/*.md`.
7. Тест добавляйте только для non-generic gate-поведения; generic managed policy уже покрывается registry/policy tests.

## 9router

1. `cp .claude/settings.local.json.example .claude/settings.local.json`
2. API key из `http://localhost:20128`

## FINISH

Канон: `.cursor/rules/shared/finish-block.mdc` → `finish-doc-router.mdc` → `/clear` (аналог new chat в Cursor).  
IMPLEMENT: step-файл + Handoff в `activeContext` **до** decompose completed.
