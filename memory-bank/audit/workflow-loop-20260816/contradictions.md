# Противоречия и неоднозначности

## P0 — ломает команды / канон

### 1. Архив ролей «живой» в роутере, в hub отсутствует

- `mainrule.mdc` → `project_manager/`, `team_lead/`, … — каталогов нет
- `CLAUDE.md`: «архив `_archive/cursor-rules/`» — **`_archive/` нет**
- ~40 slash: `pm-*`, `tl-*`, `content-*`, `marketing-*`, `seo-*` грузят `_archive/...` → битый путь
- `workflow-idea-pipeline.mdc` зависит от PM paths → IDEA с PM-фазой в hub падает

**Факт:** архив живёт в отдельных product-репо, не vendored в hub.

### 2. Missing `.cursor/rules/front-tests-parent-only.mdc`

Ссылки: `CLAUDE.md`, `token-economy-core` §0.12, `mainrule-core` FRONT, `.agents` role-command.  
Живой канон: только `.claude/rules/front-tests-parent-only.md` (+ `~/.claude/rules/02-…`).

### 3. Две копии `role-command` — разный Step 0

| | `.claude/skills/role-command` | `.agents/skills/role-command` |
|--|-------------------------------|-------------------------------|
| SECURITY graphify | execute обязателен; PLAN/DECOMPOSE skip | весь `SECURITY` в пропуске |
| front-tests path | `.claude/...` | missing `.cursor/...mdc` |

`diff` подтверждён: файлы **различаются**. Cursor catalog тянет `.agents` → другой канон, чем CLAUDE.md.

### 4. Graphify: PLAN skip ↔ INTEG PLAN требует

- Skip PLAN: `mainrule`, `graphify.mdc`, role-command
- **Требует** graphify: `integration_developer/workflow-plan.mdc` шаг 1b
- Hub: нет `.venv`/`graphify` → practice «N/A», но exception **не кодирован** в graphify.mdc

### 5. Spawn: три правды

| Документ | Политика |
|----------|----------|
| `CLAUDE.md` | IMPLEMENT L1–L2 без spawn, если paths известны |
| `token-economy` §0.12 / context-session | codebase search → обязательный `explorer` |
| `spawn-hard.md` | explorer если `MODEL_LOOP=1`; skip при `delta_paths_exist` |

### 6. CLAUDE.md leftover: implement `.md` vs yaml

- Канон `finish-block`: **FORBIDDEN** legacy `.md` implement
- CLAUDE FINISH / Session: `sNN|eNN-*.md`, Handoff из `implement-*.md`
- Риск: агент создаёт `.md` → fail validate/finalize

### 7. `load_now`: CLAUDE «ONE plan shard» vs FORBIDDEN plan в IMPLEMENT

§0.5.1 запрещает полный plan в IMPLEMENT `load_now`. CLAUDE Session start п.3 велит «ONE plan shard» → агент тащит plan.

## P1 — частые мисинтерпретации

| Тема | Как путают |
|------|------------|
| «Lean» | lean **read** vs lean **write** (§0.0 vs §0.2/§0.5) |
| Re-read | CLAUDE: абсолютный бан; `context-economy-cc`: 1× activeContext перед FINISH |
| TodoWrite ≤2 | «за IMPLEMENT» vs «за сессию»; PLAN не уточнён |
| `BLOCKED:` vs `NEED_HUMAN:` | pretool пишет BLOCKED; docs/stop — NEED_HUMAN; loop **очищает** BLOCKED |
| Handoff | CLAUDE: в implement artifact; finish-block: **только** activeContext |
| wc -l ≥ 400 | только portal INTEG, агенты обобщают на любой PLAN |
| cwd graphify | hub vs PROJECT_ROOT в multi-root |
| Parent-only front tests | граница vitest vs pytest API |

## Что solid (не путать с долгом)

1. §0.0 + §0.0.1 load≠write  
2. `plan-artifact.md` path-globs  
3. `load_now` + ONE Handoff Write-целиком  
4. Implement yaml + seed → validate → verify → finalize  
5. AC = work shard; jump `plan §N`  
6. Multi-epic + `.queue.yaml`  
7. Смысл front-tests parent-only  
8. graphify cwd = один repo root  
9. Silent tools  
10. «Нет команды роли → не грузить workflow»
