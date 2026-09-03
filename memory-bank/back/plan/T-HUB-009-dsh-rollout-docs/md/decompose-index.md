# decompose-T-HUB-009-dsh-rollout-docs / index.md

**Plan:** [plan/T-HUB-009-dsh-rollout-docs/md/plan.md](../plan/T-HUB-009-dsh-rollout-docs/md/plan.md)  
**Role:** BACK  
**Status tracker (canon):** [index.yaml](index.yaml)  
**Дата:** 2026-08-30  

---

## Outcome map (plan → steps)

| Outcome | Зачем | sNN |
|---------|-------|-----|
| `memory-bank/architecture/dsh-runtime.md` с mermaid dual-runtime diagram, env table, failure modes | Архитектурная честная картина после T-HUB-006-008; разработчик понимает как DSH подключается без чтения кода | s01 |
| `memory-bank/architecture/index.md` ссылается на dsh-runtime shard | Навигация из architecture index работает | s01 |
| `memory-bank/architecture/services.md` содержит S-DSH row + mermaid DSH fork | services.md отражает as-built dual-runtime | s01 |
| `docs/runbooks/dsh-loop-pilot.md` с prereqs, install, env, first run, troubleshooting | Разработчик проходит pilot checklist без устных инструкций; AC+1, AC+4, AC+5 | s02 |
| Pilot checklist — 10-строчная sign-off таблица с шагом verify gate parity | AC+6; human sign-off завершает pilot | s02 |
| Developer preview banner в runbook | AC− "не declare production-ready"; FR-8 | s02 |
| `loop/README.md` содержит секцию DSH Runtime (opt-in) | Оператор loop видит EPIC_RUNTIME=dsh опцию без поиска по коду; FR-5 | s03 |
| `loop/WORKFLOW.md` содержит EPIC_RUNTIME параграф | FR-5 пари с WORKFLOW | s03 |
| `README.md` (hub root) содержит pointer на dsh/ + pilot runbook | FR-6; entry point для нового разработчика | s03 |
| `dsh/README.md` содержит cross-links на architecture/dsh-runtime.md + runbook | Финальная полировка без дублирования content | s03 |
| `memory-bank/architecture/services.md` mermaid обновлён (DSH fork в loop.sh) | Диаграмма точная (углубление s01 delta) | s04 |
| `memory-bank/architecture/data-flow.md` содержит dual-runtime ветку или explicit ссылку | data-flow.md не молчит про DSH | s04 |
| Audit pass: все AC+ выполнены, env vars в docs совпадают с as-built, нет aspirational API | NFR-1 gate; inline fix если расхождение | s05 |

---

## Requirements coverage

> **HARD:** каждый AC+ / AC− / FR / NFR → ≥1 шаг, иначе явный out_of_scope.

| Req ID | Кратко | sNN | Notes |
| :--- | :--- | :--- | :--- |
| FR-1 | `docs/runbooks/dsh-loop-pilot.md`: prereqs, install, env, first run, troubleshooting | s02 | |
| FR-2 | `memory-bank/architecture/dsh-runtime.md`: diagram + env table + failure modes | s01 | |
| FR-3 | `memory-bank/architecture/index.md`: link dsh-runtime shard | s01 | |
| FR-4 | `memory-bank/architecture/services.md`: DSH as optional session executor | s01, s04 | s01 создаёт row; s04 углубляет mermaid |
| FR-5 | `loop/README.md` + `WORKFLOW.md`: EPIC_RUNTIME section | s03 | |
| FR-6 | Hub `README.md`: pointer to dsh/ + pilot runbook | s03 | |
| FR-7 | Pilot checklist AC: 10 steps sign-off table | s02 | |
| FR-8 | Explicit «not production default» в all entry docs | s01, s02, s03 | banner в каждом создаваемом файле |
| NFR-1 | Docs match as-built after 006-008 (no aspirational APIs) | s05 | audit gate + inline fix |
| NFR-2 | Russian language for memory-bank docs | s01, s04 | memory-bank/* = RU; runbook/README = EN (dev-facing) |
| NFR-3 | No duplicate of T-HUB-005 full cheatsheet — cross-link only | s03, s05 | s03 cross-link; s05 проверяет дубль |
| AC+1 | `test -f docs/runbooks/dsh-loop-pilot.md` | s02 | |
| AC+2 | `test -f memory-bank/architecture/dsh-runtime.md` | s01 | |
| AC+3 | architecture index links dsh-runtime | s01 | |
| AC+4 | Runbook: Node version, DSH pin, DEEPSEEK_API_KEY, install-profiles, EPIC_RUNTIME=dsh | s02, s05 | |
| AC+5 | Runbook troubleshooting: missing dsh, profile not found, gate deny, API 429 | s02, s05 | |
| AC+6 | Pilot checklist with sign-off row for verify gate parity | s02 | |
| AC−1 | Не declare DSH production-ready | s01, s02, s03 | developer preview banner |
| AC−2 | Не remove Claude documentation | s03 | additive-only изменения |
| AC−3 | Не auto-enable EPIC_RUNTIME in Makefile | s03 | Makefile не затрагивается |

---

## Stages coverage

| Stage (план §До DECOMPOSE) | sNN |
|----------------------------|-----|
| s01 — architecture/dsh-runtime.md + index links | s01 |
| s02 — runbook dsh-loop-pilot.md | s02 |
| s03 — loop README/WORKFLOW + hub README | s03 |
| s04 — services/data-flow touch-ups | s04 |
| s05 — review vs as-built 006-008 (audit pass) | s05 |

---

## Replacement cleanup

n/a — documentation only. Нет code replacement. Нет deletes из существующих файлов (только additive updates).

---

## Steps

| sNN | Файлы | Статус |
|-----|-------|--------|
| [s01](s01-arch-dsh-runtime-shard.yaml) | architecture/dsh-runtime.md (create); architecture/index.md (update); architecture/services.md (update) | pending |
| [s02](s02-runbook-dsh-loop-pilot.yaml) | docs/runbooks/dsh-loop-pilot.md (create); docs/runbooks/ (mkdir) | pending |
| [s03](s03-loop-readme-hub-readme.yaml) | loop/README.md (update); loop/WORKFLOW.md (update); README.md (update); dsh/README.md (update) | pending |
| [s04](s04-services-dataflow-touchup.yaml) | architecture/services.md (update mermaid); architecture/data-flow.md (update or n/a ref) | pending |
| [s05](s05-audit-vs-asbuilt-006-008.yaml) | audit pass; inline fixes if needed | pending |

## Очередь шагов

| step_id | title & files | next_phase | status |
| :--- | :--- | :--- | :--- |
| **s01** | s01-arch-dsh-runtime-shard · [yaml](s01-arch-dsh-runtime-shard.yaml) | BACK IMPLEMENT | completed |
| **s02** | s02-runbook-dsh-loop-pilot · [yaml](s02-runbook-dsh-loop-pilot.yaml) | BACK IMPLEMENT | completed |
| **s03** | s03-loop-readme-hub-readme · [yaml](s03-loop-readme-hub-readme.yaml) | BACK IMPLEMENT | completed |
| **s04** | s04-services-dataflow-touchup · [yaml](s04-services-dataflow-touchup.yaml) | BACK IMPLEMENT | completed |
| **s05** | s05-audit-vs-asbuilt-006-008 · [yaml](s05-audit-vs-asbuilt-006-008.yaml) | BACK IMPLEMENT | completed |