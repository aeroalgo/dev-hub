# Context sync — <epic_id>

**Дата:** YYYY-MM-DD  
**Роль:** BACK | FRONT | INTEG  
**Worker:** `agent_type=context-sync` (запускается parent после QA PASS)  
**Epic:** <epic_id>  
**QA evidence:** `memory-bank/{role}/qa/<epic_id>/qa-YYYYMMDD-<slug>.yaml`  
**Force:** no | yes (reason)

## Evidence used

| Source | Path / jump |
|--------|-------------|
| QA | … |
| Technology axiom | plan §… |
| Context consumed | plan §… |
| decompose-index | … |
| Root before | techContext / productContext / systemPatterns / projectbrief |

## QA retro

> Короткая запись из QA pass. Не переписывать историю и не придумывать
> выводы: взять четыре поля из `qa-*.yaml` и добавить только evidence-based
> уточнение context/patterns.

| Вопрос | Ответ |
|--------|-------|
| Какой дефект пропустили предыдущие gates? | … |
| Какой gate/check оказался лишним? | … |
| Какой тест флапает или был хрупким? | … |
| Что изменить в следующем цикле? | … |

## Changes

| File | Action | Summary |
|------|--------|---------|
| `techContext.md` | updated \| no-op | … |
| `productContext.md` | updated \| no-op | wedge / now only |
| `systemPatterns.md` | updated \| no-op | … |
| `domain/SP-*.md` | created \| n/a | … |
| `projectbrief.md` | updated \| no-op | … |
| `constitution.md` | no-op | … |
| `style-guide.md` | no-op | … |

## Rationale

- …

## Forbidden check

- [ ] Не трогали `product/vision|phases|roadmap`
- [ ] Не трогали plan/decompose/implement/code

## Return

- `status: done` → `sync_path` этого файла; loop атомарно закрывает QA и выбирает ARCHIVE / next PLAN
- `status: fail` → parent остаётся в QA и исправляет bounded blocker
