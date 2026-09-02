# Copilot Instructions for dev-hub

## Security Requirements

This project uses MEDUSA for security scanning. All code must pass security checks.

## Before Suggesting Code

- Avoid SQL injection: use parameterized queries, never string concatenation
- Avoid command injection: don't use shell=True with subprocess
- Avoid XSS: sanitize all user input before rendering
- Avoid hardcoded secrets: use environment variables
- Avoid unsafe file operations: validate paths, prevent traversal

## After Code Changes

Remind users to run security scans:
- `medusa scan .` for full scan
- `medusa scan . --quick` for cached results
- `medusa scan . -e archive/` to exclude directories

## Code Standards

- All new code must pass `medusa scan .` with no CRITICAL findings
- HIGH severity issues should be fixed before merge
- MEDIUM issues should be documented if not fixed

## Intelligent False Positive Handling

When reviewing MEDUSA scan results, distinguish real issues from false positives:

### False Positives (Don't report as issues)
- B404/B603/B607: subprocess in CLI tools, installers, build scripts
- B602: shell=variable where variable is not literal True
- B101: assert in test files (pytest standard)
- Secrets in .env.example with placeholder values

### Real Issues (Must fix)
- shell=True with user input
- High-entropy strings matching real API key patterns
- SQL with string concatenation
- eval/exec with external data

### Handling FPs
Create .bandit config:
```yaml
skips:
  - B404  # import subprocess
  - B603  # subprocess call
  - B101  # assert in tests
```

## Security Patterns by Language

Python:
- Use `subprocess.run()` with list args, not shell=True
- Use parameterized queries with SQLAlchemy or psycopg2
- Never use `eval()` or `exec()` with user input

JavaScript/TypeScript:
- Sanitize HTML output to prevent XSS
- Validate and sanitize all URL parameters
- Use `Object.create(null)` for user-controlled objects

Shell:
- Always quote variables: "$var" not $var
- Use `set -euo pipefail` in scripts
- Validate file paths before operations

Docker:
- Never run as root in production (use USER directive)
- Pin base image versions
- Don't copy secrets into images

## Configuration

Security settings are in `.medusa.yml`. For false positives, create `.bandit` config.

## Severity Levels

- CRITICAL: Must fix immediately, blocks deployment
- HIGH: Fix before merging PR
- MEDIUM: Should fix, can be follow-up
- LOW/INFO: Best practice suggestions
