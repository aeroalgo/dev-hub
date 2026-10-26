# clarify — bitrix-loop-epic-board

**plan_id:** T-HUB-108-loop-board-projection  
**slug:** bitrix-loop-epic-board (alias: loop-board-projection)  
**role:** back  
**date:** 2026-10-26  
**feature_description:** Зеркало эпиков loop во внешний таскборд через pluggable adapter (Bitrix24 | Plane); queue/loop = SoT; доска = проекция; create/move после finish.  
**status:** done

---

## Контекст и цель

- Вход: чат-решения (Linear отклонён; MCP docs ≠ live SoT; цель = «эпики ездят по внешней доске из loop»; Frappe CRM sync out-of-scope).
- **Post-clarify chat (Phase 1 amend):** pluggable board adapter — переключение провайдера **Bitrix24 | Plane** одним конфигом (не Bitrix-only).
- Цель CLARIFY: hosting/auth, coupling finish↔доска, scope ролей, момент create, карта стадий.
- Ограничения: fail-closed mapping; без silent skip; без dual SoT; MCP не основной канал.

---

## Grill pass (Phase 0 — mandatory)

| Поле | Значение |
|------|----------|
| **Reframe** | Проекция lifecycle эпика hub → внешний таскборд (Bitrix24 или Plane) через один adapter-контракт; SoT не переезжает. |
| **Premises** | 1–11 Round 1–2 — **accepted**. 12) Провайдер выбирается конфигом `provider: bitrix24|plane` — **accepted** (Phase 1 chat). 13) Общий Protocol create/move + provider-scoped mapping — **accepted**. |
| **Weakest link** | Смена provider без очистки mapping → чужой external_id; fail-closed на provider mismatch. |
| **Anti-scope** | Linear MCP; docs-only MCP как драйвер доски; Frappe CRM sync; двусторонний sync; Bitrix OAuth v1; hard-fail finish; DSH board_sync resurrect. |
| **Verdict** | `auto_resolved` после Round 2 (Evidence = Q→A) |
| **Design tree (sketch)** | ~~все узлы Round 1–2 settled~~ → PLAN HOW. |

---

## Product probe (office-hours lite)

| # | Вопрос | Контекст / Ответ |
|---|--------|------------------|
| 1 | **Demand reality** | Человекочитаемая доска эпиков в Б24. |
| 2 | **Status quo** | Фазы в activeContext / queue. |
| 3 | **Desperate specificity** | После finish люди не видят колонку. |
| 4 | **Narrowest wedge** | Cloud webhook + lazy create + STAGE_MAP + soft-fail + opt-in. |
| 5 | **Observation & surprise** | DSH board_sync снят — не resurrect. |
| 6 | **Future-fit** | Projection adapter; pluggable. |

- **Recommended wedge:** finish-hook projection, opt-in config, soft-fail.

---

## Таксономия сканирования

| Категория | Status | Notes |
|-----------|--------|-------|
| scope | Clear | projection; allowlist; anti CRM sync |
| data | Clear | epic_id map in `.loop/` |
| UX-API | Clear | REST tasks.add / stages.movetask |
| NFR | Clear | soft-fail + loud sync_error |
| integrations | Clear | cloud + webhook |
| edge | Clear | missing map → create; missing stage → error; disabled → explicit reason |
| constraints | Clear | opt-in; no OAuth v1 |
| terminology | Clear | projection ≠ SoT |
| design_skills (FRONT UI) | n/a | |

---

## Design skills pack (FRONT — при UI-scope)

n/a

---

## Frontier rounds

### Round 1 — DONE

| Q | Answer |
|---|--------|
| Q1 Hosting | A cloud |
| Q2 Finish coupling | B soft-fail |
| Q3 Role scope | C allowlist default BACK |
| Q4 Auth | A webhook |

### Round 2 — DONE

| Q | Answer |
|---|--------|
| Q5 Create trigger | A lazy on first finish |
| Q6 Stage map | C STAGE_MAP YAML + example compressed |
| Q7 Sidecar | B `.loop/bitrix-epic-map.yaml` |
| Q8 Enable | A opt-in full config; incomplete → explicit disabled reason |

Frontier empty — no Round 3.

---

## Q→A log

| # | Q | A |
|---|---|---|
| 1 | Hosting | A cloud `*.bitrix24.ru` |
| 2 | Finish coupling | B soft-fail |
| 3 | Role scope | C allowlist default `["back"]` |
| 4 | Auth | A incoming webhook |
| 5 | Create trigger | A first finish if no mapping |
| 6 | Stage map | C STAGE_MAP YAML phase→stageId |
| 7 | Sidecar | B `.loop/bitrix-epic-map.yaml` |
| 8 | Enable flag | A opt-in when webhook+group+STAGE_MAP complete |
| 9 | Multi-provider | Phase 1 chat: pluggable adapters Bitrix24 + Plane; switch via config `provider` |
| 10 | Board columns | Phase 1 chat: + **Backlog** → канон 6 колонок (backlog/design/build/verify/done/blocked) |

---

## Deferred / CRITICAL

| Marker | Topic | Status |
|--------|-------|--------|
| — | — | none open |

---

## Completion Report

**status:** done  
**Grill:** done · Verdict auto_resolved after Round 2 (+ Phase 1 amend multi-provider)  
**Rounds:** 2 · Q total: 8 + amend  
**Ready for Phase 1 PLAN:** yes  
**Chat decisions for prompt:** cloud · soft-fail · allowlist · webhook · lazy create · STAGE_MAP YAML · `.loop/` map · opt-in · **pluggable Bitrix24|Plane adapters**  
**design_pack:** n/a
