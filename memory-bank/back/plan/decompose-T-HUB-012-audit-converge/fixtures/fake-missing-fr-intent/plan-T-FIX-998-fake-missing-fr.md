# Plan — T-FIX-998 fake missing FR intent

## Intent inventory

- **FR-1 (P1):** The fixture must demonstrate an intent with no implementation or implementation evidence.
- **AC+ #4:** A dry-run AUDIT must emit a `missing` finding with `HIGH` or `CRITICAL` severity, preserve `source_ref: FR-1`, and point to a new `sNN-audit-*` remediation shard.

## Scope

This fixture intentionally contains no product code and no implement evidence for FR-1. It is a deterministic input for validating the AUDIT finding contract; it is not a production feature and must not be treated as completed implementation.
