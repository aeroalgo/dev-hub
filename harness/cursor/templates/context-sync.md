# Context sync — <epic_id>

**Дата:** YYYY-MM-DD  
**Роль:** BACK | FRONT | INTEG  
**Команда:** `* CONTEXT SYNC`  
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

## Next

- `* ARCHIVE NOW <epic_id>` | `* PLAN` next from queue
