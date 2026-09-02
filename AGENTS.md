# dev-hub

## Dev Environment

This project uses MEDUSA for automated security scanning.

### Before committing code

```bash
# Run security scan
medusa scan .

# Quick scan (uses cache, faster for incremental changes)
medusa scan . --quick

# Exclude directories from scan
medusa scan . -e archive/ -e vendor/
```

Fix any CRITICAL or HIGH severity issues before committing.

### Installing dependencies

If you see warnings about missing security tools:

```bash
medusa install --check    # See what's missing
medusa install --all      # Install all required tools
```

## Project Standards

### Security requirements

- All code changes must pass `medusa scan .` with no CRITICAL findings
- HIGH severity findings should be addressed before merge
- Use `medusa scan . --fail-on high` in CI/CD pipelines

### Code quality

MEDUSA scans for:
- Security vulnerabilities (injection, XSS, hardcoded secrets, etc.)
- Code quality issues (unused variables, complexity, etc.)
- Best practice violations (Docker as root, insecure defaults, etc.)

## Intelligent False Positive Handling

When reviewing scan results, use judgment to distinguish real issues from false positives:

### Common False Positives (Don't Fix)
| Code | Description | Why it's a FP |
|------|-------------|---------------|
| B404 | import subprocess | CLI tools need subprocess |
| B603 | subprocess call | Safe when not using shell=True |
| B607 | partial path | Tools validated before execution |
| B602 | shell=True | FP when `shell=variable` not literal True |
| B101 | assert statement | Standard in pytest test files |

### Real Issues (Must Fix)
- `subprocess.run(cmd, shell=True)` with user input
- High-entropy strings matching API key patterns (not placeholders)
- SQL built with f-strings or .format() with variables
- `eval()` or `exec()` with any external data

### How to Handle FPs Project-Wide
Create a `.bandit` config file:
```yaml
skips:
  - B404  # import subprocess - this is a CLI tool
  - B603  # subprocess without shell - safe usage
  - B101  # assert in tests - pytest standard
```

This reduces noise from 70+ findings to just real issues.

## Configuration

Security scanning is configured in `.medusa.yml`:

```yaml
fail_on: high     # Fail CI on high+ severity
exclude:
  paths:
    - node_modules/
    - .venv/
    - dist/
```

To exclude false positives, add paths or files to the exclude section.

## Testing

After making changes, verify security compliance:

```bash
# Full scan
medusa scan .

# Generate HTML report for review
medusa scan . --report html
```

Python tests (hub): `bin/pytest …` from repo root — 300s timeout built into wrapper.

Reports are saved to `.medusa/reports/`.

## Troubleshooting

**Scan shows "tool not found"**: Run `medusa install --all`

**Too many false positives**: Create `.bandit` config with appropriate skips

**Slow scans**: Use `medusa scan . --quick` for cached results

---

*Security scanning powered by [MEDUSA](https://github.com/Pantheon-Security/medusa)*
