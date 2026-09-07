## Epic

### Outcome

Управляемый dev-hub проект явно сообщает стек каждого target, а workflow и skills получают проверяемую capability без знания команд конкретного языка. Rust, Python и JavaScript становятся равноправными встроенными профилями, не создавая arbitrary shell runner.

### In

- Typed project manifest и локальный registry profiles.
- Безопасное разрешение verify-first capabilities в argv/cwd contract.
- Явные targets, JS manager policy, doctor и migration project config.

### Out

Marketplace, remote profiles, установка skills, lifecycle/deploy operations, исполнение target scripts и изменение self-test хаба.

### Done when

1. Три профиля детерминированно разрешают заявленные capabilities для явного target.
2. Неоднозначный target/profile/lockfile/legacy config не даёт fallback и не исполняет команду.

### Forbidden after

Dynamic shell command path, implicit Python/JS fallback, recursive manifest search, `project.yaml` как второй config SoT, смешение runtime adapter и stack profile.

### Chat decisions

- V1 = profiles + capabilities; не plugin platform.
- JS: lockfile-first, explicit override при ambiguity.
- Manifest отдельный от `.dev-hub`; named monorepo targets; verify-first vocabulary.

---

## Covering

n/a — single epic
