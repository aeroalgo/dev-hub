## Epic

### Outcome
Заявленный machine-path должен совпадать с тем, что реально запускается. Учить один вход, принимать другой, или принимать запись после падения валидатора — ложный green. Доктор/CLI/extract не имеют права быть мягче канона.

### In
- операторский вызов = тот же контракт, что runtime
- extract не dual-path: нет prose-salvage рядом с typed
- doctor не маскирует scan warn’ом из-за неверного вызова
- искать leftover-пути извлечения, не один хелпер

### Out
новый schema/ownership · session pipeline redesign · pack executable graph

### Done when
1. copy-paste из агента не падает на несуществующем флаге
2. repair/extract не принимает прозу, если typed path обязателен
3. architecture/boundary scan не скрыт неверным API вызова

### Forbidden after
soft-accept после exception validate · тест, который **требует** prose fallback · doctor warn вместо fail на сломанном вызове

### Chat decisions
- три конкретных drift’а (CLI flag, doctor kwargs, repair prose) — leftover, не новый продукт
- axiom «JSON fence = sole extract SoT» здесь дожимается, не переписывается

---

## Covering

n/a — single epic
