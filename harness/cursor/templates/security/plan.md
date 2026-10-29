# SECURITY PLAN — <id>

> **SUSPENSION GUARD active** — plan output **maximally detailed / unlimited** (§0.0).  
> Chat brief OK. **FORBIDDEN:** TOC-only · telegraph · size cap на этот файл.

**Дата:** YYYY-MM-DD  
**Режим:** BACK SECURITY PLAN | FRONT SECURITY PLAN | APP SECURITY PLAN | INTEG SECURITY PLAN
**Статус:** draft | active | done  
**Scope:** S (one-shot) | M/L (эпик)

## Контекст

- role scope: BACK api/auth/db/jobs | FRONT client/XSS/CSP | APP contract/API/UI/wire | INTEG wire/authz
- refs: techContext, architecture/, prior security-audit-*
- out of scope: …

→ `plan/<plan_id>/yaml/decompose-index.yaml` — **после DECOMPOSE:** единственный трекер aNN

## Inventory surfaces

| Surface | Paths / routes | Threat class | Priority |
|---------|----------------|--------------|----------|
| … | … | authz / injection / XSS / supply-chain / … | Critical\|High\|Medium\|Low |

## Threat model

- assets: …
- actors: …
- entry points: …
- trust boundaries: …

## SQL / querystring filter SoT (BACK — если есть)

Dataflow: querystring → validators → ORM QueryBuilder / `build_sql_query` → DB.  
Call sites, residual SQLi vs identifier/over-filter, partner_id binding.

## Candidate findings (inventory — не execute)

| ID | Sev | Path:line | OWASP | Note |
|----|-----|-----------|-------|------|
| … | Critical\|High\|… | … | … | **не** копировать plaintext secrets |

## Priority matrix

1. Critical — …
2. High — …
3. Medium — …
4. Low — …

## Skills map

| Surface / aNN | Audit skills (paths) |
|---------------|----------------------|
| … | `.agents/skills/…/SKILL.md` |

## Evidence commands (для execute)

```bash
# cwd = repo root
rg -n '…' …
```

## До DECOMPOSE (черновик нарезки)

Outline `aNN` **без** checkbox-статусов. После DECOMPOSE — сжать/удалить; детали → `aNN-*.yaml`.

| draft | surface | files |
|-------|---------|-------|
| a01 | … | … |

## Assumptions

…

## AC эпика

1. Каждый Critical/High surface закрыт `aNN` findings
2. Findings → actionable BUGFIX/IMPLEMENT (ID + severity + evidence)
3. Out-of-scope явно зафиксирован
4. Нет root `security-audit-*.md` параллельно с эпиком

## Следующий режим

→ `* SECURITY DECOMPOSE`
