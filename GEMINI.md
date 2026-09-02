# dev-hub

## Commands

```bash
# Security scan
medusa scan .

# Quick scan (cached)
medusa scan . --quick

# Exclude directories
medusa scan . -e archive/ -e vendor/

# Install tools
medusa install --all
```

## Slash Commands

- `/medusa-scan` - Run security scan
- `/medusa-install` - Install missing tools

## Security Standards

- All code must pass `medusa scan .` with no CRITICAL findings
- Fix HIGH severity issues before committing
- Configuration: `.medusa.yml`

## Severity Levels

- CRITICAL: Fix immediately
- HIGH: Fix before commit
- MEDIUM: Should fix
- LOW/INFO: Optional

## Intelligent False Positive Handling

When reviewing MEDUSA scan results, intelligently triage findings:

### Common False Positives
- **B404/B603/B607**: subprocess usage in CLI tools, build scripts, installers - legitimate
- **B602**: `shell=variable` where variable isn't `True` (e.g., `shell=self.detect_shell()`)
- **B101**: assert in test files - standard pytest practice
- **Secrets**: `.env.example` with placeholders like `xxx`, `your-key-here`

### Real Issues (Fix These)
- `shell=True` with user-controlled input
- High-entropy strings that look like real API keys/tokens
- SQL queries built with string concatenation
- `eval()`/`exec()` with external input

### Handling FPs
1. Create `.bandit` config with `skips:` for project-wide rules
2. Add test fixtures/vendor code to `.medusa.yml` exclude paths
3. Use `# nosec BXXX` comments only as last resort (document why)

### Example .bandit
```yaml
skips:
  - B404  # import subprocess - CLI tool
  - B603  # subprocess call - validated input
  - B101  # assert in tests
```
