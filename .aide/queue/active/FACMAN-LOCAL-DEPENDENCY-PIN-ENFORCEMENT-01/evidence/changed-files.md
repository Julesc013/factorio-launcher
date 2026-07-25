# Local dependency pin enforcement changed-file intent

- `tools/verify_dependency_revisions.py` now exposes a reusable read-only
  verifier with portable environment and explicit path resolution.
- `tools/workspace_config.py doctor` verifies both sibling `HEAD`s.
- `tools/dev.py verify-all` checks pins before building or testing.
- `tools/package/pipeline.py` checks pins before package output ownership,
  cleaning, staging, or creation.
- Focused tests prove current-pin success, mismatch refusal, path precedence,
  and absence of implicit checkout.
- Developer, testing, tooling, and release documentation state the behavior.

No workspace lock pin or sibling repository state changed in this WorkUnit.
