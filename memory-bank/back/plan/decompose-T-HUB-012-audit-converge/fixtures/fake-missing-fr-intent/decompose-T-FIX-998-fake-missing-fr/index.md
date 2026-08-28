# Decompose fixture — T-FIX-998 fake missing FR intent

## Purpose

Dry-run fixture for the post-IMPLEMENT AUDIT path. `FR-1` is present in the plan but intentionally has no code or implementation evidence. A conforming audit reports the intent as `missing` with `HIGH` or `CRITICAL` severity and appends a remediation shard instead of silently treating a stub as coverage.

## Steps

| Step | Status | Coverage |
|---|---|---|
| `s01-stub` | pending fixture stub | Does not cover `FR-1`; no implementation evidence |

## Expected remediation

The audit finding must point to `sNN-audit-fake-missing-fr.yaml` (or an equivalent new `sNN-audit-*` path) and carry `source_ref: FR-1` into the shard `goal` and `plan_refs`.
