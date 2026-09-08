# HARD — Claude Code runtime adapter

Общая политика gate, verdict, ALLOW и repair-loop находится в
`harness/instructions/spawn-hard.md` и обязательна без изменений.

Claude Code transport overlay:

- запускай субагентов через `Agent` с canonical `subagent_type`;
- для gate-run передавай packed `BLOCKERS` / `ALLOW` / `VERIFY` sections;
- дождись завершения `Agent` перед обработкой verdict;
- при `FAIL`, `BLOCKED` или repairable runtime error запускай
  `gate-repair`, дождись repair и повторяй тот же gate-agent;
- alias `verify` / `reviewer` разрешён только по общей карте gate-агентов.

Этот overlay не дублирует общую политику и не может её ослабить.
