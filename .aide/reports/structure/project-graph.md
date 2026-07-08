# Factorio Launcher ProjectGraph Baseline

Status: `PASS_WITH_WARNINGS`
Files classified: `1319`
Findings: `9`

## Counts By Kind

- `aide_governance`: 815
- `aide_local_template`: 6
- `doc`: 102
- `frontend_shell`: 9
- `implementation`: 220
- `package_manifest`: 16
- `product_policy`: 30
- `public_abi`: 32
- `schema`: 29
- `test`: 29
- `tool`: 11
- `unknown`: 20

## Findings

### FLAUNCH-PG-001 - warning

native command graph not yet implemented

- Expected: source/ulk/command should contain real registry, schema routing, dry-run, audit, and handlers
- Observed: currently scaffolded; Python prototype remains runnable behavior
- Recommendation: Build command registry before more GUI work.
- Next task: `AIDE-BUILD-ULK-COMMAND-REGISTRY-V0-01`

### FLAUNCH-PG-002 - warning

Python prototype is still current runnable CLI

- Expected: Python should be prototype and golden behavior harness only
- Observed: pyproject exposes factorio-launcher from source/prototypes/python_launcher
- Recommendation: Port commands into native command graph while preserving CLI JSON behavior.
- Next task: `AIDE-BUILD-FACTORIO-PROTOTYPE-PARITY-MAP-01`

### FLAUNCH-PG-003 - info

universal setup and launcher are incubated/planned siblings

- Expected: FLaunch may incubate until API pressure is proven, but must not own universal semantics permanently
- Observed: include/source/schemas currently contain usk and ulk namespaces
- Recommendation: Discuss universal repo structure separately before large native code expansion.
- Next task: `AIDE-BUILD-USK-ULK-SPLIT-READINESS-REPORT-01`

### FLAUNCH-PG-004 - pass

source/ is the only implementation source root

- Expected: no src/, launcher/, nested source/, or app-local src/ roots
- Observed: structure policy and filesystem match this rule
- Recommendation: Keep this rule unless a deliberate structure redesign replaces it.
- Next task: `FLAUNCH-CANON-STRUCTURE-01`

### FLAUNCH-PG-005 - pass

apps/ contains shells, not product logic

- Expected: frontend implementation should live under source/apps
- Observed: apps roots contain shell/readme/project files; implementation roots exist in source/apps
- Recommendation: Keep apps shell-only.
- Next task: `FLAUNCH-APPS-SHELL-CHECK-01`

### FLAUNCH-PG-006 - pass

Factorio repo must not implement install mutation

- Expected: repair, uninstall, rollback, and destructive setup mutation belong to Universal Setup
- Observed: docs and policies state this boundary
- Recommendation: Keep setup mutation behind handoff/adapter boundaries.
- Next task: `AIDE-BUILD-USK-SPLIT-READINESS-REPORT-01`

### FLAUNCH-PG-007 - pass

dry-run default must remain true

- Expected: launch plans should be previewed unless execution is explicit
- Observed: README, product policy, and AIDE safety policy encode dry-run
- Recommendation: Keep execution opt-in.
- Next task: `FLAUNCH-SAFETY-REGRESSION-CHECK-01`

### FLAUNCH-PG-008 - pass

no Factorio binaries may be bundled

- Expected: package manifests and product policy must forbid bundling Factorio binaries
- Observed: package/security checks enforce this
- Recommendation: Keep packaging checks in CI.
- Next task: `FLAUNCH-PACKAGING-AUTHORITY-REPORT-01`

### FLAUNCH-PG-009 - pass

production legacy packages must not depend on Python or AIDE

- Expected: AIDE and Python prototype are development/prototype surfaces only
- Observed: package check and structure policy enforce runtime separation
- Recommendation: Keep AIDE and Python out of package manifests.
- Next task: `FLAUNCH-RUNTIME-DEPENDENCY-CHECK-01`
