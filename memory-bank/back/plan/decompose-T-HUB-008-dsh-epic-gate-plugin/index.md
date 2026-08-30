# [T-HUB-008 | dsh-epic-gate-plugin] DECOMPOSE

**Дата:** 2026-08-30  
**Режим:** BACK DECOMPOSE  
**Эпик:** T-HUB-008  
**Статус:** pending  
**Plan:** [plan-T-HUB-008-dsh-epic-gate-plugin.md](../plan-T-HUB-008-dsh-epic-gate-plugin.md)  
**Deps:** T-HUB-006 (runtime adapter), T-HUB-007 (presets), T-HUB-016 (cc-hooks-bridge)

---

## Контекст / Scope

T-HUB-008 закрывает только дыры DSH bridge (T-HUB-016), без которых epic workflow ломается:

| Gap | DSH Limitation | Owner |
|-----|---------------|-------|
| A | PreToolUse Agent `updatedInput` unavailable → rewrite/deny | T-HUB-008 |
| B | SubagentStart `agent_type` unavailable → typed identity missing | T-HUB-008 |
| C | SubagentStop transcript/verdict missing → VERDICT не зеркалируется | T-HUB-008 |
| D | SessionStart first-turn semantics → unclear bridge behaviour | T-HUB-008 |

Все остальное (Stop self-limit, bridge install, версии DSH, UserPromptSubmit, Bash Pre/Post) — T-HUB-016.

---

## Queue

| Step | File | Description | Next phase | Status |
|------|------|-------------|------------|--------|
| **s01** | s01-spawn-validate-extract.yaml | Spike updatedInput ADR + extract spawn_validate.py + unit tests | BACK IMPLEMENT | completed |
| **s02** | s02-agent-type-preset-mapping.yaml | agent_type normalization в subagent-start.py + preset lookup + tests | BACK IMPLEMENT | completed |
| **s03** | s03-epic-gate-cordis-plugin.yaml | Cordis epic-gate plugin (PreToolUse spawn gate) wired to profiles | BACK IMPLEMENT | completed |
| **s04** | s04-verdict-mirror-subagent-stop.yaml | SubagentStop VERDICT extraction + mirror to Python subagent-stop.py | BACK IMPLEMENT | completed |
| **s05** | s05-session-start-first-turn.yaml | SessionStart first-turn semantics — research + fix or no-op | BACK IMPLEMENT | completed |
| **s06** | s06-gate-check-turn-conditional.yaml | gate-check-turn.py — conditional, skip if bridge Stop sufficient | BACK IMPLEMENT | completed |
| **s07** | s07-mount-parity-readme-integration.yaml | Mount order + parity README + integration smoke suite | BACK IMPLEMENT | completed |
| **s08** | s08-audit-native-agent-type-mapping.yaml | Audit remediation: native typed agent identity and preset contract | BACK IMPLEMENT | completed |
| **s09** | s09-audit-pretool-integration-smoke.yaml | Audit remediation: native pre-execute deny and bridge round-trip smoke | BACK IMPLEMENT | completed |
| **s10** | s10-audit-runtime-export-contract.yaml | Audit remediation: explicit project-root and hub export contract | BACK IMPLEMENT | completed |
---

## Requirements coverage

| Requirement | Description | Steps |
|-------------|-------------|-------|
| FR-001 | spawn updatedInput rewrite (PATH_A) or deny-only (PATH_B) | s01, s03 |
| FR-002 | spawn_validate.py library extracted | s01 |
| FR-003 | typed subagent identity — agent_type normalization | s02 |
| FR-004 | preset mapping: verify, reviewer, explorer | s02 |
| FR-005 | VERDICT mirror via SubagentStop enrichment | s04 |
| FR-006 | gate-check-turn.py (conditional — only if bridge Stop fails FINISH) | s06 |
| FR-007 | SessionStart first-turn semantics | s05 |
| NFR-1 | Zero TS rewrite of Python hook logic | s01, s03, s04, s05 |
| NFR-2 | spawn_validate extractable for Cordis | s01 |
| NFR-3 | Fail-closed при misconfigured bridge | s03 |
| NFR-4 | Parity README covers all gaps with owner/status | s07 |
| AC+1 | Incomplete verify spawn → deny with stable reason code | s01, s03 |
| AC+2 | agent_type/preset mapping covers verify, reviewer, explorer | s02 |
| AC+3 | VERDICT PASS → mirror evidence visible to stop-gate / state | s04 |
| AC+4 | Parity README lists gaps A–D closed or deferred with owner | s07 |
| AC+5 | Claude path zero regression | s07 |
| AC−1 | Не удалять/заменять Python stop-gate/agent-pretool для Claude | s01, s03 |
| AC−2 | Не портировать bash-pretool/user-prompt/session-start в TS | s01, s03 |
| AC−3 | Не дублировать 016 bridge | s03 |
| AC−4 | Не default EPIC_RUNTIME=dsh | s05 |
| AC−5 | Не раздувать plugin до «всех hooks» | s03, s04 |
| SC-002 | gap matrix ≥ 5 rows with owner epic (закрыты/deferred) | s07 |

---

## Stages coverage

| План §канон | Shard | Статус |
|-------------|-------|--------|
| spike: updatedInput ADR (rewrite vs deny) | s01 | pending |
| extract spawn_validate.py + tests | s01 | pending |
| agent_type normalization + preset map | s02 | pending |
| epic-gate Cordis plugin scaffold + PreToolUse handler | s03 | pending |
| SubagentStop VERDICT mirror | s04 | pending |
| SessionStart first-turn (research + optional fix) | s05 | pending |
| gate-check-turn.py (conditional) | s06 | pending |
| mount order + parity README + regression smoke | s07 | pending |

---

## Outcome map

1. **spawn_validate.py создан** — валидация spawn выделена как переиспользуемая библиотека → закрывает: s01 (FR-002, NFR-2)
2. **updatedInput ADR зафиксирован** → epic-gate реализует PATH_A или PATH_B → закрывает: s01, s03 (FR-001, AC+1)
3. **agent_type normalization в subagent-start.py** → typed identity при DSH runtime → закрывает: s02 (FR-003, FR-004, AC+2)
4. **SubagentStop VERDICT mirror** → stop-gate и state видят VERDICT при DSH runtime → закрывает: s04 (FR-005, AC+3)
5. **SessionStart first-turn** → либо confirmed bridge-ok (no-op), либо fix в session-start.py → закрывает: s05 (FR-007)
6. **gate-check-turn.py или skip** → если bridge Stop достаточен — skip; иначе thin turn counter → закрывает: s06 (FR-006)
7. **Parity README + regression smoke** → все gaps A–D documented closed/deferred; Claude path зелёный → закрывает: s07 (AC+4, AC+5, NFR-4, SC-002)

---

## Replacement cleanup

| Action | What | Replacement | Shard | Cleanup | Notes |
|--------|------|-------------|-------|---------|-------|
| extract (move logic) | inline spawn validation в agent-pretool.py main() | spawn_validate.py import | s01 | agent-pretool.py main() укорачивается; логика в spawn_validate.py | Python-side; TS не трогается |
| update status | dsh/README.md gap rows owner=T-HUB-008 open | T-HUB-008 closed | s07 | строки заменяются, не удаляются | документальная замена |
| no-op | «PLAN 2026-08-22 full TS port of agent-pretool + stop-gate» | bridge-first + gap plugin | s01 (ADR) | отмечено в plan revision; не требует delete кода | уже зафиксировано в plan revision 2026-08-27 |
