# Шаг aNN: <title>
**Plan ID:** <plan_id>
**Next Phase:** BACK SECURITY | FRONT SECURITY | INTEG SECURITY
**needs_creative:** no

> **Policy:** статус шага здесь не хранить. Статус — в `implement/aNN-*.yaml` (`epic-security/v1`) и `decompose/index.md`.

---

## Skills meta (HARD — канон для SECURITY execute)

**audit_surface:** auth | api | sql | secrets | deps | ci | client | wire | headers | jobs | other

**Audit skills (REQUIRED Read до аудита)** — concrete paths only:
- `.agents/skills/owasp-security-check/SKILL.md`
- `.agents/skills/security-auditor/SKILL.md`
- …

Cap: ≤8 skills на шаг. FORBIDDEN: «(если…)» вместо пути.

---

## Цель
<одна-две строки: какой surface / threat class закрыть findings-артефактом>

## Scope
- **Paths:** `apps/…`, `frontend/…`, routes, CI files
- **Consumes:** plan inventory row, prior aNN (если depends)
- **Produces:** `security/implement/implement-<id>/aNN-<slug>.yaml` — findings + severity + evidence

## Threats / OWASP focus
- …

## Evidence commands
1. …
2. …

## Подробный процесс
1. Orient (graphify query по scope)
2. Read Audit skills
3. Audit → evidence
4. Write findings artifact (Critical→Low)
5. Не чинить код; фиксы → BUGFIX/IMPLEMENT

## Чекпоинт верификации
- Findings файл создан по шаблону execute
- Каждый finding: severity, location, evidence, suggested fix mode
- Out-of-scope шага не раздут
