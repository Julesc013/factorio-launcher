# Data Model

Core records:

- product manifest
- install reference
- instance manifest
- launch profile
- launch plan
- modset lockfile
- save index
- account reference
- export manifest
- diagnostic report

All persisted records must be human-readable JSON or TOML and must avoid
machine-local absolute paths unless marked non-portable.

## Contract validation level

`contracts/policy/live_schema_subset.v1.toml` identifies schemas used by live
commands, persisted objects, refusals, and package verification. The repository
validator implements a documented JSON Schema subset and now rejects a live
schema if it contains a keyword or type the validator cannot enforce. Unknown
types no longer pass by default, and dynamic properties, string patterns,
numeric bounds, and array bounds are checked.

This is an experimental supported-subset claim, not a claim of complete JSON
Schema Draft 2020-12 conformance. A standards-conforming vetted validator is
still preferred before schema stability or third-party/network inputs.
