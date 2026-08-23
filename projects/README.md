# projects/

Optional per-slug environment overrides for dev-hub projects.

currently unused. Intended structure:

```
projects/<project-slug>/  # одна папка per project
  .env.override           # env vars override (не в git)
  config.local.yaml       # local config overrides
```

When a project slug matches, dev-hub tooling (bin/, loop/) can source
these overrides before starting the loop or running commands.

No files here = no overrides applied (default behaviour).
