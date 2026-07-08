# Factorio Launcher ProjectGraph Baseline

Status: `PASS_WITH_WARNINGS`
Files classified: `1141`
Findings: `9`

## Counts By Kind

- `aide_governance`: 815
- `aide_local_template`: 6
- `doc`: 108
- `frontend`: 41
- `implementation`: 39
- `package_manifest`: 16
- `product_policy`: 30
- `public_abi`: 10
- `schema`: 16
- `test`: 30
- `tool`: 11
- `unknown`: 19

## Findings

### FLAUNCH-PG-001 - warning

native command graph not yet implemented

- Expected: universal-launcher should contain real registry, schema routing, dry-run, audit, and handlers
- Observed: split repo is scaffolded; native FacMan CLI currently owns the smoke behavior
- Recommendation: Build command registry in universal-launcher before more GUI work.
- Next task: `AIDE-BUILD-ULK-COMMAND-REGISTRY-V0-01`

### FLAUNCH-PG-002 - pass

Python product runtime is retired

- Expected: Python should be tooling, fixtures, validators, and tests only
- Observed: apps/python_cli and product pyproject.toml are removed; native facman is built by CMake
- Recommendation: Keep product runtime entrypoints native.
- Next task: `AIDE-BUILD-FACTORIO-PROTOTYPE-PARITY-MAP-01`

### FLAUNCH-PG-003 - info

universal setup and launcher are sibling repositories

- Expected: FacMan must not own universal setup or launcher runtime implementation
- Observed: Factorio repo keeps only include/flb and runtime/factorio; universal code moved out
- Recommendation: Harden universal repo validators before large native code expansion.
- Next task: `AIDE-BUILD-USK-ULK-SPLIT-READINESS-REPORT-01`

### FLAUNCH-PG-004 - pass

source/ and src/ are retired

- Expected: no src/, source/, launcher/, product/, universal/, data/, schemas/, or packaging roots
- Observed: structure policy and filesystem match this rule
- Recommendation: Keep retired roots blocked.
- Next task: `FLAUNCH-CANON-STRUCTURE-01`

### FLAUNCH-PG-005 - pass

apps/ contains frontend entrypoints and presentation

- Expected: reusable behavior should live under runtime/ or universal repos
- Observed: app roots use role names and do not contain nested src/source directories
- Recommendation: Keep app roots thin.
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

- Expected: AIDE and Python are development tooling surfaces only
- Observed: package check and structure policy enforce runtime separation
- Recommendation: Keep AIDE and Python out of package manifests.
- Next task: `FLAUNCH-RUNTIME-DEPENDENCY-CHECK-01`
