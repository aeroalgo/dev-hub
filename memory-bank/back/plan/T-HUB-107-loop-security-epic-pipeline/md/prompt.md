## Epic

### Outcome
Оператор может вести SECURITY-эпик через loop по шагам аудита так же машинно, как feature по шагам реализации: после декомпозиции курсор двигается по audit-шагам, принимает findings-артефакт, и завершает эпик без ложного feature-хвоста AUDIT/QA.

### In
- Различение видов эпика и путей plan/execute по виду
- Фаза audit-execute с gate и schema findings
- Завершение audit-эпика в DONE без кодового QA-хвоста
- Паритет path resolve для соседнего kind с тем же контрактом путей

### Out
- Проведение самих security-аудитов продуктового кода как содержание эпика
- Изменение feature lifecycle ANALYZE→IMPLEMENT→AUDIT→QA
- Затягивание one-shot SECURITY без эпика в loop
- Новые agent runtimes / смена Claude↔Codex

### Done when
1. `start`/`run`/`finish` на security-эпике резолвит index под security/plan и двигает aNN по одному
2. Попытка закрыть шаг без валидного findings-артефакта fail-closed
3. После последнего aNN курсор = DONE; нет требования AUDIT/QA для этого kind
4. Hardcode «только feature plan/» на hot path start/finish/prompt нельзя использовать без ошибки

### Forbidden after
optional kind defaulting к feature при явном security path · dual path index_path feature-only + security side-lookup · reuse verify-implement как sole gate для audit · silent skip schema · ANALYZE/QA как обязательный хвост security kind

### Chat decisions
- SECURITY в loop: DECOMPOSE → SECURITY @aNN* → DONE (без ANALYZE/AUDIT/QA/CONTEXT_SYNC)
- Epic kind: feature | refactor | security; auto-detect + `--kind` при неоднозначности
- Новый gate verify-security; schema epic-security/v1
- S one-shot без эпика остаётся вне loop
- Refactor path parity в том же эпике (та же kind-инфраструктура)
- Фиксы findings — отдельные BUGFIX/IMPLEMENT, не SECURITY

---

## Covering

n/a — single epic
