# Copilot Instructions for dev-hub

## Security Requirements

All code must follow secure coding practices.

## Before Suggesting Code

- Avoid SQL injection: use parameterized queries, never string concatenation
- Avoid command injection: don't use shell=True with subprocess
- Avoid XSS: sanitize all user input before rendering
- Avoid hardcoded secrets: use environment variables
- Avoid unsafe file operations: validate paths, prevent traversal

## Code Standards

- Fix CRITICAL and HIGH severity security issues before merge
- MEDIUM issues should be documented if not fixed

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

## Severity Levels

- CRITICAL: Must fix immediately, blocks deployment
- HIGH: Fix before merging PR
- MEDIUM: Should fix, can be follow-up
- LOW/INFO: Best practice suggestions
