# projects/

Optional per-slug environment overrides for dev-hub projects. The loop's base
configuration is the hub root `.env`.

currently unused. Intended structure:

```
projects/<project-slug>/  # одна папка per project
  .env.override           # env vars override (не в git)
  config.local.yaml       # local config overrides
```

When a project slug matches, dev-hub tooling (bin/, loop/) can source
these overrides before starting the loop or running commands.

No files here = no overrides applied (default behaviour).

## Canonical deployment manifests

Deployment is intentionally centralized in `dev-hub`, not copied into each
product. Each managed product has one manifest at:

```text
projects/<project-basename>/deploy.json
```

The common runner is `bin/devops-deploy`. Its Python implementation is
`bin/devops-deploy.py`. It accepts
only `check`, `status`, `apply`, and `rollback`, invokes the exact Python
adapter declared by the manifest, and performs the declared SSH, unit,
container, listener, TCP, and HTTP checks. `apply` is fail-closed:

```bash
"$DEV_HUB/bin/devops-deploy" --project "$PWD" check --json
"$DEV_HUB/bin/devops-deploy" --project "$PWD" apply
```

Do not put shell snippets, arbitrary SSH commands, passwords, tokens, or
private keys in the manifest. Start a new project from
`harness/templates/devops-deploy.json` and add only allowlisted targets and
endpoints.
