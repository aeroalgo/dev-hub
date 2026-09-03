---
paths:
  - "app/**"
  - "api/**"
  - "core/**"
  - "jobs/**"
  - "tests/**"
  - "migrations/**"
---

# Backend code conventions

Role commands on backend code → `.claude/skills/role-command/SKILL.md` with prefix **BACK**.

- FastAPI + SQLAlchemy 2 async patterns
- TDD for new logic (workflow-implement)
- Integration §0.11: grep every route/key/env/column ↔ migration/consumer
- UI work → hand off to FRONT workflow (`front_developer/mainrule.mdc`)
