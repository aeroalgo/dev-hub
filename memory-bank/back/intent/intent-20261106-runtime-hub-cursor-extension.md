# Intent — Runtime Hub → Cursor application

**date:** 2026-11-06  
**status:** committed-direction (после T-HUB-109)  
**related:** T-HUB-109-runtime-hub · clarify-20261106-runtime-hub  

---

## Решение (не забыть)

Целевой UX оператора — **приложение/расширение для Cursor**, не отдельная Electron/Tauri IDE и не «навсегда только CLI».

### Зачем
- Вести **несколько проектов параллельно**
- Каждое **окно Cursor = папка проекта + свой чат**
- В окне выбирать **аккаунт + модель (+ runtime)** и работать
- Другое окно/вкладка проекта — другой profile, без путаницы state

### Архитектура направления

```text
T-HUB-109  runtime_hub CLI (engine: profiles, adapters, fail-closed)
    ↓
T-HUB-110+ Cursor extension (UI): workspace-scoped profile picker
    ↓
несколько окон Cursor = параллельные проекты
```

- **CLI Hub** — фундамент и SoT профилей (`~/.dev-hub/runtime-hub/`).
- **Cursor extension** — оболочка: выбрать profile для этого workspace/окна, вызвать `hub-runtime use`, не spoof OAuth.
- **Параллелизм** — штатные окна Cursor, не свой multi-tab IDE.
- **Не делать** отдельный desktop chat-клиент «вместо Cursor», пока extension не упрётся в потолок.

### Анти-амнезия

| Сейчас (T-HUB-109) | Дальше (обязательное направление) |
|--------------------|-----------------------------------|
| CLI-only MVP | Cursor extension / app UI |
| UI out-of-scope эпика | UI in-scope следующего эпика |
| loop wire deferred | отдельно, не блокирует Cursor UI |

### Следующий эпик (когда DECOMPOSE/IMPLEMENT 109 не блокирует)

- Рабочий id-кандидат: **T-HUB-110-runtime-hub-cursor-extension**
- Роль: FRONT (+ BACK wire к `hub-runtime`)
- Команда старта: `FRONT PLAN` / `BACK PLAN` по slug `runtime-hub-cursor-extension` после готовности CLI ядра

### Ссылки

- Plan 109: `memory-bank/back/plan/T-HUB-109-runtime-hub/md/plan.md`
- Clarify: `memory-bank/back/clarify/clarify-20261106-runtime-hub.md`
- Chat: 2026-11-06 — «нужна возможность вести сразу несколько проектов параллельно… окно с чатом… модель аккаунт»
