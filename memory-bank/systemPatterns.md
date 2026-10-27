# System patterns — index (dev-hub)

| ID | Pattern |
|----|---------|
| SP-H01 | Hub vs product split: tooling в `dev-hub`, артефакты/код продукта в `PROJECT_ROOT` |
| SP-H02 | Context-first cursor: `activeContext.md` + decompose `index.yaml` + implement step |
| SP-H03 | Runner owns session bounds; agent owns step content / Handoff |
| SP-H04 | Fail-closed на checkpoint/index conflict, malformed config, model substitution |
| SP-H05 | `hub-link`: symlink rules/templates/agents/hooks/skills → product tree (canonical `harness/` layer → `.claude/` symlink shell) |
| SP-H06 | Loop cwd = hub; product через `--add-dir $PROJECT_ROOT` |
| SP-H07 | Gate subagents: `verify` / `reviewer` / `explorer` (spawn policy) |
| SP-H08 | Roadmap queue YAML opt-in (`EPIC_CHAIN_ROADMAP=1`) после `EPIC_DONE` |
| SP-H09 | Epic kinds & lifecycle layout: `Cursor.kind` (`feature`, `refactor`, `security`) определяет plan/index/execute paths и lifecycle (security: aNN findings `epic-security/v1` -> DONE без AUDIT/QA хвоста) |
| SP-H10 | Board projection: внешний таскборд как зеркало фазы эпика (Bitrix24, Plane). Protocol `BoardProjectionAdapter` + registry; post-finish hook; loop остаётся SoT; soft-fail на REST-ошибках без отката cursor; fail-closed на несовпадении provider в sidecar identity map (`.loop/board-epic-map.yaml`) |
