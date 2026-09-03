# IDEA: <название>

**ID:** T-xxx  
**Slug:** <slug>  
**Created:** YYYY-MM-DD  
**Status:** intake | active | done  
**Intent:** positioning | feature_ui | feature_api | feature_full | content | growth | initiative  
**PM-L:** L1 | L2 | L3 | L4  
**DEV-L:** L1 | L2 | L3 | L4  

## Идея

<1–3 предложения от пользователя>

## Связь с продуктом

- productContext: …
- systemPatterns: …

## Decision / Scorecard

| Поле | Значение |
|------|---------|
| Problem | … |
| Users | … |
| Success metric | … |
| Alternatives considered | … |
| Risks | … |
| **Verdict** | `go` \| `needs-clarification` \| `kill` |
| Kill rationale | *(заполнить только при verdict=kill)* |
| Pipeline status | `done/killed` *(обязательно при verdict=kill; terminal outcome)* |
| Next after kill | `terminal` *(при verdict=kill; не назначать `PLAN`/`IMPLEMENT`)* |
| Blocking questions | *(обязательно при verdict=needs-clarification; каждый item сохраняет evidence и marker `[НУЖНО УТОЧНИТЬ: CRITICAL …]`)* |
| Revisit stage | `CLARIFY` *(обязательно при verdict=needs-clarification; указать следующую роль-команду после уточнения, если она уже известна)* |

## Pipeline

| # | Фаза | Команда | Статус | Артефакт |
|---|------|---------|--------|----------|
| 1 | … | PM DISCOVER MARKET | pending | — |
| 2 | … | MARKETING PLAN | pending | — |

## Skills

- …

## Risks / open questions

- …

## Handoff

- **Done:** …
- **Artifact:** …
- **Next:** …
- **Tool / model:** Cursor + fast-editing | Claude Code + premium-coding
- **New chat:** yes | no

### Handoff-on-go

Заполняется обязательно при `Verdict: go` до назначения или запуска следующей role command. Все пять полей должны быть непустыми.

- **Problem:** …
- **Approach:** …
- **In:** …
- **Out:** …
- **Metrics:** …
- **Open questions:** …

При `Verdict: kill` этот подраздел не заполняется: вместо него в `## Decision` фиксируются `Kill rationale`, `Pipeline status: done/killed` и `Next after kill: terminal`; следующие role commands не назначаются.
