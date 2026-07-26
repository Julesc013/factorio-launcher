# Local dependency pin enforcement validation

- `python tools/verify_dependency_revisions.py`: Pass.
- `python tools/workspace_config.py doctor`: Pass against exact ULK
  `7bd4425f0c35414f738159b45d8bec42edf70235` and USK
  `3f8489275077347c2918f3bb03614ec6431362ff`.
- Focused dependency, workspace, package-pipeline, test-architecture, and
  release-structure tests: Pass, 26 of 26.
- Default mismatch proof: Pass; two drifts reported and `run_git` was not
  called.
- `python tools/strict_check.py`: Pass.

Package preflight calls the verifier before any output-root ownership check or
mutation. `verify-all` calls it before the full native/Python gate.
