# Workflow — полный цикл

```
brief → plan → keyframes → generate → audio → assemble → qc → out/final.mp4
```

## Фазы

| Фаза | Вход | Выход | Агент делает |
|------|------|-------|----------------|
| plan | `briefs/*.md` | `work/project.yaml` (+ script при необходимости) | shot list, промпты, timing |
| keyframes | yaml shots | `work/shots/Sxx_key.png` | image gen / Comfy / API |
| generate | image_ok shots | `work/shots/Sxx.mp4` | i2v предпочтительно |
| audio | script / style | `work/audio/*` | VO, bed, caps track |
| assemble | clips + audio | `work/assembly/master.mp4` | Kinocut / FFmpeg / Remotion |
| qc | master | `work/qc/*` | contact sheet, redo list |
| done | qc pass | `out/final.mp4` | copy + tag phase=done |

## Статусы shot

`pending` → `image_ok` → `video_ok` → `done`  
ветка: `redo` / `blocked`

## DSH

1. Открыть web UI, cwd / workspace = эта папка `test_project`
2. Следовать `AGENTS.md`
3. MCP: см. `dsh/mcp.patch.example.yml`

## Перенос в ~/VideoProject

См. `INSTALL.md` в корне `test_project`.
