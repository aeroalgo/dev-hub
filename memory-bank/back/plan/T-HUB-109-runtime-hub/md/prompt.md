## Epic

### Outcome
Оператор из одной CLI-точки выбирает профиль (runtime + аккаунт + модель), активирует изолированное окружение и запускает официальный агентский бинарь провайдера. Auth остаётся у нативного CLI; хаб не проксирует subscription OAuth.

### In
- Профили с изолированными home-dir для нескольких аккаунтов одного runtime
- Адаптеры spawn: Codex, Claude Code, Antigravity
- Команды use / status / run / doctor / list с fail-closed ошибками
- Codex по умолчанию native; OmniRoute только явным профилем
- SoT профилей вне git репозитория хаба

### Out
- Desktop / Cursor extension UI
- Подключение loop как SoT runtime/model
- HTTP OpenAI-bridge над Antigravity
- Извлечение/replay OAuth токенов в чужой HTTP-клиент
- Публичный shared gateway
- Автомиграция login state между профилями
- Удаление OmniRoute wrapper из репозитория (только смена default policy)

### Done when
1. `hub-runtime use <profile>` активирует isolated home и записывает active profile
2. `hub-runtime run` стартует бинарь выбранного runtime с env профиля; без бинаря — non-zero + причина
3. Неизвестный profile / конфликт active без `--force` — non-zero, без silent fallback на `~/.codex`
4. Профиль Codex без OmniRoute не выставляет OmniRoute wrapper как executable
5. Профиль `agy` spawn-only: нет локального HTTP bridge в MVP
6. Секреты и profile homes не коммитятся в dev-hub

### Forbidden after
OAuth spoof proxy · silent fallback на global homes · dual default Codex path (Hub native + OmniRoute default без opt-in) · «модуль есть, CLI не fail-closed» · tracked API keys · auto-copy login между profiles · loop hard cutover в этом эпике

### Chat decisions
- MVP = CLI only (без UI в этом эпике)
- Runtimes MVP: Codex + Claude Code + Antigravity
- Аккаунты = isolated profile dirs
- Loop wire — later / opt-in, не SoT в MVP
- OmniRoute: native Codex default; OmniRoute только explicit profile/flag
- agy: spawn-only, без HTTP bridge
- Layout: `~/.dev-hub/runtime-hub/`
- Ошибки: fail-closed
- **North star после CLI:** приложение для Cursor (extension): несколько окон = несколько проектов; в каждом — чат + выбор аккаунта/модели; не отдельная Electron IDE

---

## Covering

n/a — single epic
