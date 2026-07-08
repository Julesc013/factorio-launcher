# AIDE Lite Integration

AIDE Lite is repo-local development tooling for FacMan. It is not a launcher
runtime dependency and must not be included in production packages.

The imported pack comes from `Julesc013/aide` `main` at:

```text
7d8bf19d878fd9ad29859a6cba4b7de64ad80ecc
```

The pack was regenerated from that checkout before import. Safe import copied
portable `.aide/` files, `.aide.local.example/`, target guidance, reference
docs, and local-state ignore rules. It did not copy AIDE source roots, raw
prompts, raw responses, credentials, or `.aide.local/`.

## Boundary

AIDE may help with:

- context packets
- repo maps
- verifier reports
- review packets
- Git workflow policy
- structure inventories
- root authority checks
- advisory refactor planning

AIDE must not become:

- a launcher runtime dependency
- a packaging dependency
- a provider/model/network requirement
- an autonomous mutation system
- a substitute for tests, schemas, or human structure decisions

## Target Facts

The target profile lives at `.aide/profile.yaml`.

Current target facts:

- Project name: FacMan / factorio-launcher.
- Purpose: unofficial Factorio launcher and isolated instance manager.
- Runtime boundary: production packages must not depend on AIDE.
- Python boundary: Python is allowed for repo tooling, validators, fixtures,
  and tests, but not for FacMan product runtime entrypoints.
- Native direction: stable C-compatible ABI, native kernels, CLI/TUI/daemon,
  and platform GUI shells over the command graph.
- Safety invariants: no bundled Factorio binaries, no ownership bypass, no
  credentials in manifests, no silent default data-dir writes, dry-run launch
  plans by default.

## Local State

Local AIDE state belongs under `.aide.local/` and is ignored by Git.

Portable AIDE framework files under `.aide/` are committed. Target-specific
policy files use the `flaunch-` prefix:

```text
.aide/policies/flaunch-root-authority.yaml
.aide/policies/flaunch-product-boundaries.yaml
.aide/policies/flaunch-safety.yaml
```

## Useful Commands

```powershell
py -3 .aide/scripts/aide_lite.py doctor
py -3 .aide/scripts/aide_lite.py snapshot
py -3 .aide/scripts/aide_lite.py index
py -3 .aide/scripts/aide_lite.py repo inventory
py -3 .aide/scripts/aide_lite.py repo validate
py -3 .aide/scripts/aide_lite.py repo status
py -3 .aide/scripts/aide_lite.py quality ledger
py -3 .aide/scripts/aide_lite.py quality validate
py -3 .aide/scripts/aide_lite.py git policy
py -3 .aide/scripts/aide_lite.py git plan
```

For substantial tasks:

```powershell
py -3 .aide/scripts/aide_lite.py pack --task "Implement read-only install discovery parity in native command graph"
python tools/strict_check.py
py -3 .aide/scripts/aide_lite.py verify --changed-files
py -3 .aide/scripts/aide_lite.py review-pack
py -3 .aide/scripts/aide_lite.py commit check --latest
```

`py -3 .aide/scripts/aide_lite.py test` is not part of the required FacMan
proof path after safe import. In this import mode, broad AIDE source roots are
intentionally skipped, and optional self-tests that import those source roots
may fail. Do not vendor AIDE source roots into FacMan just to make optional
AIDE self-tests green.

## First AIDE Baseline Task

Use this before large code work:

```text
Establish Factorio Launcher AIDE baseline: document architecture, safety
invariants, native CLI checks, native command graph gap, and first WorkUnits
for read-only install discovery plus isolated instance creation.
```
