# Validation

## Local conversion

- Source ZIP: `E:\Downloads\Setup_FactorioSpaceAge_2.0.77.exe.zip`
- ZIP SHA-256: `28FE2D0CEA12F9C984C681E3D0B85D75BB4B1166DB02EC3C68B89C75EFC578D9`
- Setup executable SHA-256:
  `3BC6B4A411E2D9CBE6EC791BAB95430A54242EDAACD29F2D1D97EBFC3450ECA2`
- Authenticode: valid, signer `Wube Software Ltd`
- Installer exit: 0
- Installed program: Factorio 2.0.77, build 84539, Win64 full
- Existing sibling: Factorio 2.1.10, build 86940, Win64 full
- Retained rollback: 19,750 files, 5,051,512,236 bytes, no root reparse
- New 2.0 tree: 19,742 files, 5,052,185,219 bytes, official config routing
  and local `unins000.exe`/`unins000.dat`
- Retained 2.1 tree: 20,807 files, 5,360,232,244 bytes
- Registry snapshot SHA-256:
  `ADF502912D6B3CAD4C673CB835C3A0A1FD175E75362F10960947675DE1924219`
- Restored Add/Remove Programs owner: Factorio Space Age 2.1.10 at
  `D:\Games\Factorio\2.1`
- The publisher setup auto-launched Factorio 2.0 once. Before the exact new
  process was stopped, five files in the shared AppData tree had timestamps in
  the operation window: `.lock`, `crop-cache.dat`, `factorio-current.log`,
  `config/default_config.ini`, and
  `temp/currently-playing-background/freeplay.lua`. No pre-operation AppData
  snapshot exists, so those changes were recorded rather than reversed.

## FacMan behavior

- Explicit scan of `D:\Games\Factorio`: 16 structural numeric candidates,
  zero invalid parent candidate; 2.0 now reports `official_installer`,
  `system_shared`, `separated`, and `uninstaller_present`.
- All 16 version roots are registered as read-only foreign install references.
- `factorio-2-0` imported 13 files / 4,867,764 bytes before replacement;
  instance verification passes with no warnings.
- Post-install launch preflight passes and reports `website_installer`; reads
  `D:\Games\Factorio\2.0\data` while configuration, mods, saves, logs, script
  output, and write data remain under the instance workspace.
- Strict execution remains refused with `isolation_not_proven`; no real Play
  authority was inferred from the version smoke.

## Repository gates

- `installs describe`: projects the compatible install reference into source,
  deployment, authority, data, integration, health, provenance, and filesystem
  evidence; the live 2.0.77 install remains a read-only reference.
- `installs reconcile plan`: independently reproducible evidence, desired-state,
  and plan SHA-256 digests; explicit provider/policy dependencies,
  blockers/risks/rollback, `mutation_executed=false`, and
  `apply_available=false`.
- Disposable fixture proof: a missing source blocks materialisation; a raw
  caller-selected source remains `selected_unverified` and blocked pending
  authenticated inspection. Installation, selected source, and workspace
  bytes remain unchanged and no candidate target is created.
- `flb_factorio_install_model_smoke`: pass.
- Focused CLI model, reconciliation, and command-graph tests: 2 pass.
- Historical live `factorio-2-0` proof remains valid for the read-only
  projection: version 2.0.77, `vendor_installed`, management class `reference`,
  mutation authority false, and source identity not yet bound. Its earlier
  provider-review-ready plan identity is superseded by the stricter Gate 1
  source-trust contract; a raw source reference can no longer unblock it.
- Native proof covers reference, legacy managed, proof-backed managed and
  adopted, Steam, package-manager, damaged, mutable-data-conflated, and shared
  vendor-registration cases. It also proves changed evidence or desired state
  changes plan identity and unknown enum values refuse as `invalid_request`.
- CLI proof independently reconstructs all three canonical digests, validates
  all affected schemas, confirms closed step effects, snapshots installation,
  source, and workspace bytes, and proves missing-workspace reads create no
  directory.

- PowerShell operation script parser: pass
- `tools/strict_check.py`: pass, including 250 schemas and 123 commands
- `tests.test_aide_compaction`: 6 tests pass
- Full `tools/dev.py verify-all`: pass in 499.7 seconds; 44 native tests and
  358 Python tests pass with one expected Python skip
- Gate 1 canonical local matrix: `tools/dev.py test --full` passes 43/43 native
  tests and 359 Python tests with seven declared optional skips; the full
  strict validator chain passes with 250 schemas, 123 commands, and 217 refusal
  codes.
- Portable AIDE Lite self-test: pass. Task inspection reports the active work
  unit as `partial` with zero missing evidence; noop-check says to continue
  from current status and evidence rather than repeat completed work.
