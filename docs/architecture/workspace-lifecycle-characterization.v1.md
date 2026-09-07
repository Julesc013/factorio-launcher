# Workspace lifecycle characterization v1

Status: executable pre-Alpha.6 baseline.

`tests/fixtures/workspace-lifecycle/current-behavior.v1.json` is the closed
twelve-state corpus captured before the Alpha.6 lifecycle contract changes.
`tests/test_workspace_lifecycle_characterization.py` executes one probe for
every corpus entry and proves that observation-only paths do not create or
rewrite workspace state.

The baseline confirms safe behavior for future/corrupt state, foreign roots,
link traversal, contended migration locks, interrupted journals, and foreign
staging. It also records the v1 limitations as limitations rather than implied
capabilities: the public migration projection has no root identity, workspace
revision, inventory digest, plan digest, operation identity, or write-capacity
classification. A stale plan therefore cannot be expressed at the v1 command
boundary. Read-only capability is discovered only when a mutation is attempted.

This corpus is historical evidence for the replacement contract. Alpha.6 may
strengthen an observation, but it must not regress any fail-closed or
preservation behavior captured here.
