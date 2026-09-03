# SECURITY PLAN — <id>

**Дата:** YYYY-MM-DD  
**Режим:** BACK SECURITY PLAN | FRONT SECURITY PLAN | INTEG SECURITY PLAN  
**Статус:** draft | active | done  
**Scope:** S (one-shot) | M/L (эпик)

## Контекст

- role scope: BACK api/auth/db/jobs | FRONT client/XSS/CSP | INTEG wire/authz
- refs: techContext, architecture/, prior security-audit-*
- out of scope: …

→ [decompose-…/index.md](decompose-…/index.md) — **после DECOMPOSE:** единственный трекер aNN

## Inventory surfaces

| Surface | Paths / routes | Threat class | Priority |
|---------|----------------|--------------|----------|
| … | … | authz / injection / XSS / supply-chain / … | Critical\|High\|Medium\|Low |

## Threat model (кратко → детали ниже)

- assets: …
- actors: …
- entry points: …

## Priority matrix

1. Critical — …
2. High — …
3. Medium — …
4. Low — …

## Skills map

| Surface | Audit skills (paths) |
|---------|----------------------|
| … | `.agents/skills/…/SKILL.md` |

## До DECOMPOSE (черновик нарезки)

Outline `aNN` **без** checkbox-статусов. После DECOMPOSE — сжать/удалить; детали → `aNN-*.md`.

| draft | surface | files |
|-------|---------|-------|
| a01 | … | … |

## AC эпика

1. Каждый Critical/High surface закрыт `aNN` findings
2. Findings → actionable BUGFIX/IMPLEMENT (ID + severity + evidence)
3. Out-of-scope явно зафиксирован

## Следующий режим

→ `* SECURITY DECOMPOSE`
