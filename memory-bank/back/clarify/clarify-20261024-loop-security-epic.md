# clarify — loop-security-epic

**plan_id:** T-HUB-107-loop-security-epic-pipeline  
**slug:** loop-security-epic  
**role:** back  
**date:** 2026-10-24  
**feature_description:** Стандартизировать SECURITY-эпик в loop: kind-aware paths, фаза SECURITY по шагам aNN, gate verify-security, DONE без feature AUDIT/QA.  
**status:** done

---

## Контекст и цель

- Вход: chat — SECURITY pipeline «как IMPLEMENT, но audit»; затем «стандартизировать и добавить в loop по шагам»; затем `BACK PLAN`
- Цель Phase 0: зафиксировать lifecycle SECURITY в loop и границы (refactor path, S one-shot, post-queue)
- Spike? нет

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Loop должен вести SECURITY-эпик по `aNN` так же машинно, как feature по `sNN`, но без кодовых фаз AUDIT/QA; findings → отдельный BUGFIX/IMPLEMENT. |
| **Premises** | 1) После DECOMPOSE security-эпика next = SECURITY @aNN, не ANALYZE — `accepted` (chat + proposal). 2) После всех aNN → DONE (не AUDIT/QA/CONTEXT_SYNC) — `accepted`. 3) Epic kind ∈ {feature, refactor, security} с path resolve — `accepted`. 4) REFACTOR path fix ∈ том же эпике (та же kind-инфраструктура), не отдельный mega-scope — `accepted`. 5) S one-shot `* SECURITY` без эпика остаётся вне loop — `accepted`. 6) Новый gate `verify-security`, не reuse verify-implement — `accepted`. |
| **Weakest link** | Оставить hardcode `plan/<epic>/` в CLI/prompts → security start «не видит» index. |
| **Anti-scope** | Не писать сами security-аудиты продукта; не менять feature AUDIT/QA lifecycle; не тащить S one-shot в loop; не IMPLEMENT в PLAN. |
| **Verdict** | `auto_resolved` (Evidence: pre-plan chat design + user `BACK PLAN`) |

---

## Product probe

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | Demand reality | Оператор хочет `bin/loop.py` по aNN как по sNN |
| 2 | Status quo | Workflow SECURITY есть; loop path только feature `plan/` |
| 3 | Desperate specificity | `start --epic` не резолвит `security/plan/<id>` |
| 4 | Narrowest wedge | kind resolve + SECURITY finish/advance + verify-security + schema |
| 5 | Observation | REFACTOR phase уже в gate map, но paths тоже feature-only |
| 6 | Future-fit | Новые kinds = тот же resolver, не отдельный supervisor |

- **Recommended wedge:** kind SoT + security vertical slice + refactor path parity в том же эпике.

---

## Таксономия сканирования (финал)

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear | loop SECURITY epic; S out; feature QA unchanged |
| data | Clear | cursor.kind; paths by kind |
| UX-API | Clear | CLI `--kind`; start/finish aNN |
| NFR | Clear | fail-closed ambiguous kind |
| integrations | Clear | gate agent + materialize |
| edge | Clear | missing artifact / wrong schema |
| constraints | Clear | no ANALYZE/QA for security kind |
| terminology | Clear | aNN ≠ sNN; SECURITY ≠ IMPLEMENT |

---

## Q→A log

### Q1 (chat)
- **Question:** SECURITY = тот же pipeline что IMPLEMENT?
- **Answer:** Параллельный (PLAN→DECOMPOSE→execute aNN); audit-only; фиксы отдельно.
- **resolution:** resolved

### Q2 (chat)
- **Question:** Добавить в loop по шагам?
- **Answer:** Да; kind + SECURITY phase + DONE без AUDIT/QA.
- **resolution:** resolved

### Q3 (chat)
- **Question:** PLAN vs сразу код?
- **Answer:** `BACK PLAN` — этот clarify + Phase 1.
- **resolution:** resolved

---

## Completion Report

```markdown
## Completion Report
- Grill: done (auto_resolved from chat)
- Taxonomy: all Clear for PLAN
- Q asked: 3 / 3 (chat-pre)
- CRITICAL open: 0
- Ready for Phase 1 PLAN: yes
- Outcome prompt Chat decisions: security loop DECOMPOSE→SECURITY aNN→DONE; kind feature|refactor|security; verify-security; S one-shot out of loop; refactor path in same epic
```
