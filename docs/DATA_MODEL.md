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

