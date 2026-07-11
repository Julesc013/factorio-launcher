# Roadmap

FacMan proves the universal launcher with real Factorio workflows while
leaving setup mutation to Universal Setup.

## Current R3.4 architecture consolidation

The native architecture now uses generated metadata, shared core/platform
primitives, repositories, typed transactions, decomposed application handlers,
a client-only CLI, truthful frontend transports, module-local CMake, and a
reproducible install-tree package pipeline. Test impact routing and compact
AIDE state are implemented; supply-chain policy is the remaining mandatory
R3.4 work unit. Historical R3.2/R3.3 sections below remain evidence context,
not the active queue. Ordered future gates live in
[`future_layers_plan.md`](architecture/future_layers_plan.md).

## Immediate Safety And Truth Gates

The bounded R3 gates in
[`docs/quality/safety_proof_gates.md`](quality/safety_proof_gates.md) passed for
the selected Windows CLI package lane:

1. `FACMAN-EVIDENCE-LOCK-01`
2. `FACMAN-TRUST-BOUNDARY-HARDEN-01`
3. `FACMAN-TRUTH-FLOOR-01`
4. `FACMAN-COMMAND-VERTICAL-SLICE-01`
5. `FACMAN-PACKAGE-PROOF-02`

Repository ownership and root grammar are frozen. R3.2 now concentrates on
authoritative registry introspection, run-preview routing, and the instance
isolation foundation. The public ABI remains an experimental correctness floor.

R3.2 is integrated and frozen at the
[`public integration checkpoint`](release/checkpoints/r3.2-public-integration-proof.md).
Further execution work belongs to the human-gated real Factorio isolation
WorkUnit rather than an extension of R3.2.

## R3.2 - Authoritative Registry And Instance Isolation Foundation

1. Reconcile project and AIDE truth without runtime changes.
2. Derive Universal Launcher command introspection from runtime descriptors.
3. Route canonical `run.preview` and `launch_plan.preflight` through the
   registered Factorio handler into typed application operations.
4. Correct and preflight the effective Factorio configuration, add an exclusive
   per-instance lock, and prove process-boundary isolation with a purpose-built
   test probe. Completed for the controlled process boundary; real Factorio is
   still unproven.
5. Keep real Factorio execution unpromoted until the operator smoke passes.
6. Completed the read-only Universal Setup package-verification stretch and
   the bounded diagnostic traversal foundation without enabling mutation or
   diagnostic export.

## FACMAN-INTEGRATION-HARDEN-01

- Cross-repo boundary proof for `factorio-launcher`, `universal-launcher`, and
  `universal-setup`.
- Command, result, refusal, diagnostic, and golden-output contracts.
- Stale-doc and package-layout readiness checks.
- Product-only and full sibling-workspace validation modes.

## FACMAN-PACKAGE-PROOF-02

- One explicit `windows_portable_cli_x64` target, not an OS-neutral portable
  ABI claim.
- Static-first CLI payload with no unused shared kernels or unproved
  entrypoints.
- Executable-relative package discovery and runtime SHA-256 manifest
  verification.
- Target/linkage identity, manifest closure, sibling source revisions, and
  required-resource enforcement.
- Spaces, Unicode, relocation, arbitrary working directory, read-only files,
  external workspace, archive extraction, missing-resource, and payload-drift
  tests.
- Local, unsigned, and unpublished; publisher authenticity remains deferred.

## FacMan-CANON-01

- Repo structure uses `runtime/content/contracts/release`.
- Product identity is FacMan.
- Python product runtime is retired; Python remains tooling/tests only.
- Native CLI/TUI/daemon scaffold builds.
- Native CLI owns the initial smoke commands for product inspect, doctor,
  install import, instance create, launch-plan preview, and dry-run run.
- Validators block retired roots and old GUI app layout.

## ULAUNCH-MIN-01

- Minimal Universal Launcher owns product registry, install refs, instances,
  profiles, account refs, artifact sets, launch plans, diagnostics, and command
  JSON I/O.
- No Factorio logic enters Universal Launcher.

## FacMan-DISCOVERY-01

- `facman product inspect`
- `facman doctor`
- `facman installs scan`
- `facman installs inspect <install-id>`
- `facman installs import <path>`
- JSON output for read-only reports.
- No installing, repairing, uninstalling, or downloading.

## FACMAN-DISCOVERY-FIXTURES-02

- Deterministic fake install matrix under `tests/fixtures/factorio_installs/`.
- Fixture manifests declare source, ownership, platform, capability,
  validation, and setup-mutation expectations.
- `facman installs scan --search-root <root> --json` classifies fixture roots
  without host-machine discovery.
- `facman doctor --search-root <root> --json` reports invalid explicit
  candidates without mutating fixture trees.
- Golden reports under `tests/golden/discovery/` pin read-only discovery
  summaries.
- Real Windows discovery is implemented with read-only Steam registry roots,
  bounded `libraryfolders.vdf` parsing, standalone roots, deterministic
  de-duplication, Unicode and long paths, malformed-metadata handling, and
  junction refusal.
- macOS Spotlight and Linux package-manager provider databases remain deferred.

## FacMan-INSTANCE-01

- `facman instances create <name> --install <install-id>`
- `facman instances list`
- `facman launch-plan <instance>`
- `facman run <instance> --execute` returns `isolation_not_proven` until the
  real Factorio operator smoke passes
- Default run mode remains dry-run.
- No silent writes to global Factorio data.

## FacMan-MODSET-01

- Local ZIP mod import.
- Modset lockfile generation.
- Modset verification.
- Modset export.

## FACMAN-MODZIP-DEPTH-02

- Deterministic synthetic local mod ZIP matrix under
  `tests/fixtures/factorio_mods/`.
- `info.json` parsing for name, title, version, Factorio version, author,
  description, dependencies, optional dependencies, hidden-optional
  dependencies, and incompatibilities.
- Lockfiles pin local filenames, SHA-1, SHA-256, source, enabled state, and
  structured dependency declarations.
- Goldens under `tests/golden/modsets/` pin valid lockfiles and invalid ZIP
  refusals.
- Mutation-invariant tests prove source ZIPs are not modified and invalid
  imports do not partially install.
- Mod Portal networking, account login, remote dependency solving, and setup
  mutation remain deferred.

## FACMAN-SAVE-ROUNDTRIP-02

- Deterministic synthetic save fixture matrix under
  `tests/fixtures/factorio_saves/`.
- Save backup writes sidecar manifests with source, destination, timestamp,
  SHA-1, and SHA-256 metadata.
- Save backup, clone, export, and import refuse existing targets instead of
  overwriting silently.
- Malformed save ZIPs return structured `save_malformed` refusals before
  backup, clone, or export writes outputs.
- Instance import preflights archive safety and target existence before writing
  restored instance files.
- Export/import tests prove saves roundtrip, config secrets are redacted, and
  source save fixtures are not mutated.
- Steam Cloud mutation, deep save parsing, map preview, save benchmarking, and
  save-associated modset inference remain deferred.

## FACMAN-DIAGNOSTIC-REDACTION-02

- Redaction policy contracts cover field-name, path-name, key-value, pattern,
  binary-file, archive-file, and allowed-metadata rules.
- `runtime/factorio/diagnostics/` owns deterministic text redaction, sensitive
  path exclusion, binary/archive skips, and redaction report JSON.
- `facman diagnostics redact <file> --json` proves deterministic and
  idempotent text redaction.
- `facman diagnostics redact <file> --json` handles known line-oriented inputs
  and sensitive multiline JSON string fields; malformed JSON and INI fail
  closed.
- The bundle collector uses allowlisted, deterministic, no-follow
  traversal with maximum depth, file count, per-file size, total size, and time
  budgets. It emits a structured omission report and covers spaces, Unicode,
  long paths, overlapping roots, and link/reparse refusal through shared path
  safety primitives.
- `facman diagnostics export` and doctor-bundle output route through the
  registered typed operation. Selected files are reopened from stable
  no-follow handles, limited to reviewed formats, hashed before and after
  redaction, staged through the production archive writer, journaled, and
  self-verified after commit.
- Unknown formats are omitted explicitly. Malformed reviewed structured files,
  multiply linked sources, read races, unredacted private paths, or incomplete
  traversal refuse the complete export.
- The claim remains limited to reviewed local formats and local filesystems;
  it is not general arbitrary-file sanitization or shared-filesystem proof.
- Factorio account login, credential-store implementation, diagnostic upload,
  Mod Portal token behavior, and GUI diagnostic UX remain deferred.

## FACMAN-LINUX-CLI-PACKAGE-PROOF-03

- One explicit `linux_portable_cli_x64` tarball contains the functional CLI,
  required contracts/content, manifests, licenses, and minimal documentation.
- The Ubuntu 24.04 x64 gate records sibling revisions, compiler, linker, glibc
  baseline, ELF identity, inspected system dependencies, and the absence of
  `RPATH`/`RUNPATH`.
- Zero-skip runtime proof covers spaces, Unicode, renamed extraction, arbitrary
  working directory, empty `PATH`, an external workspace, and a read-only
  package root.
- Integrity proof rejects missing, modified, extra, linked, wrong-target,
  wrong-architecture, and incomplete payloads before safe archive extraction
  and post-extraction smoke.
- The claim is package-preview evidence for that runner and dependency set,
  not universal Unix support or a completely static binary.

## FACMAN-LOCAL-FILESYSTEM-LOCK-HARDEN-03

- Run and recovery locks retain an exclusive platform handle for the complete
  operation and record Windows volume/file ID or POSIX device/inode identity.
- Release revalidates the held handle and current path before deleting only the
  exact owned lock object.
- Links, reparse points, hostile substitution, renamed parents, stale metadata,
  and concurrent ownership fail closed without deleting a replacement path.
- Remote, unclassified, or unreviewed filesystem types refuse. SMB, NFS,
  cloud-sync, and multi-host safety remain explicitly unpromoted.

## FACMAN-SBOM-AND-PROVENANCE-01

- Built packages contain a hash-closed SPDX 2.3 document covering FacMan,
  Universal Launcher, Universal Setup, and Miniz dependency/license truth.
- Adjacent provenance binds the final artifact digest to exact source and dirty
  state, workspace lock, component/hash/SBOM manifests, toolchain, CI identity,
  and a source-commit UTC timestamp policy.
- Mutation tests reject drift in every recorded identity or digest.
- The record is unsigned and unpublished: provenance is recorded, while
  publisher authenticity remains explicitly unproven.

## FACMAN-MACOS-NATIVE-CLI-PROOF-01

- One explicit `macos_portable_cli_x64` tarball contains only the functional
  CLI, contracts/content, manifests, licenses, and minimal documentation.
- The `macos-15-intel` gate builds the complete native core, runs all CTests,
  portable Python and strict checks, then records x86_64 Mach-O identity,
  deployment target 13.0, SDK/toolchain, inspected system dependencies, and
  the absence of `LC_RPATH`.
- Zero-skip package proof covers integrity, relocation, spaces, Unicode,
  arbitrary working directory, empty `PATH`, external workspace, read-only
  package root, SPDX/provenance, safe extraction, and post-extraction runtime.
- Apple Silicon, universal binary, broader macOS compatibility, AppKit runtime,
  signing, notarization, release, and publication remain unproven.

## FacMan-SETUP-HANDOFF-01

- Managed install commands call Universal Setup.
- Ownership classes distinguish managed, foreign-owned, imported, and portable
  installs.
- Steam remains foreign-owned.

## FacMan-GUI-01

- WinForms, WinUI, AppKit, SwiftUI, GTK, and Qt frontends render the same
  command graph from OS-first GUI lanes.
- No GUI-only behavior.

## Release Readiness Ladder

```text
R0 - Architecture baseline
  validators pass
  contracts exist
  cross-repo builds pass

R1 - Developer preview
  fake fixtures
  dry-run launch plans
  no real mutation

R2 - Local power-user alpha
  real install import
  fixture-backed discovery classification
  instance layout and launch-plan scaffolding
  controlled process-spawn fixture proof
  real Factorio write isolation not proven
  execute quarantined until isolation proof
  local modsets
  workspace invariants and package layout skeletons
  save roundtrip and diagnostic redaction proofs

R3 - Portable package and safety hardening
  shared trust-boundary regressions pass
  unsafe capabilities are proven or explicitly unavailable
  one authoritative install-to-launch-preview command slice
  one target-specific static CLI package
  package integrity and relocation smoke

R4 - Managed install alpha
  Universal Setup local archive install
  verify/uninstall managed only

R5 - Native GUI preview
  WinForms/AppKit first shells over command graph

R6 - v1.0
  stable CLI
  stable schemas
  portable packages
  no known boundary violations
```

## Future Contract Layers

The next layer is tracked in
[`docs/architecture/future_layers_plan.md`](architecture/future_layers_plan.md).
That plan keeps capability/effect policy, refusal codes, workspace contracts,
package contracts, customization, accessibility, redaction, runtime/client
ownership, Universal Setup transaction work, and diagnostic intelligence as
bounded work units on top of the current structure.

R2 product hardening status and follow-up work units are tracked in
[`docs/product/r2_alpha_hardening.md`](product/r2_alpha_hardening.md).
