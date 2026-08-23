# Установка test_project в ~/VideoProject

Из этой сессии Cursor не смог писать в `~/VideoProject` (каталог был `root:root`). Выполни один раз в своём терминале:

```bash
sudo chown -R "$USER:$USER" ~/VideoProject
cp -a /home/aero/PyProject/dev-hub/_scratch/VideoProject/test_project ~/VideoProject/
# или из /tmp, если копировал туда:
# cp -a /tmp/VideoProject_test_project ~/VideoProject/test_project

cd ~/VideoProject/test_project
ls -la
```

## Запуск с DSH

```bash
cd ~/VideoProject/test_project
npx @deepseek-ai/dsh web
# или твой установленный: dsh web
```

В чате:

> Прочитай AGENTS.md и briefs/demo.md. Выполни только фазу plan: дополни image_prompt/video_prompt в work/project.yaml. Файлы медиа не создавай.

## MCP

Скопируй куски из `dsh/mcp.patch.example.yml` в свой DSH profile patch (`~/.dsh/profiles/web/…`), поправь пути под себя. Сначала filesystem/workspace, потом kinocut, потом gen.
