# FacMan Project State

## Summary

FacMan is an unofficial Factorio launcher and isolated instance manager. The
three-repository ownership split and durable root grammar are frozen. Universal
Setup owns installed-state mutation, Universal Launcher owns product-neutral
runnable-state orchestration, and this repository owns Factorio semantics and
Factorio-facing applications.

## Current Phase

R3.3 production data paths, recovery, and cross-platform proof.

R3.2 is integrated on `dev` at
`b739d271083c2883c94921a1441574cda55912ad`, with Universal Launcher `main` at
`80a848375227dc858865874ef594c4b466877241` and Universal Setup `main` at
`4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2`. The checkpoint is frozen. Its
human-gated real Factorio claim remains pending independently while R3.3
addresses archive, transfer, recovery, diagnostics, and Linux package
foundations that do not require a Factorio binary.

## Current Proof

- The five migrated commands `install_refs.scan`, `install_refs.import`,
  `install_refs.inspect`, `instance.create`, and `launch_plan.build` execute
  through the authoritative Universal Launcher route.
- Path traversal, unmanaged cleanup, and silent persistent overwrite have
  committed adversarial regression coverage.
- A Windows x64 static-first package proof exists for the CLI-only lane.
- Public sibling revisions are pinned by
  `release/index/workspace_lock.v1.toml` and checked before three-repository
  builds.
- Windows read-only discovery is implemented for Steam registry roots, bounded
  `libraryfolders.vdf` parsing, standalone roots, deterministic de-duplication,
  Unicode and long paths, malformed metadata, and junction refusal.
- The public C ABI is experimental. Its current proof is a correctness floor,
  not a stable third-party compatibility promise.
- Universal Launcher introspection is generated from retained runtime
  descriptors, and canonical `run.preview` plus `launch_plan.preflight` route
  through the registered Factorio application handler into typed results.
- Instance creation and import generate the effective Factorio `config.ini`;
  preflight parses that same file and refuses mismatched, sensitive, or linked
  roots.
- A purpose-built process probe proves argument transfer, intended writes,
  protected-root invariance, and exclusive run-lock behavior. This evidence is
  not a substitute for a real Factorio operator verdict.
- The real-Factorio operator harness records executable, revision, OS, and
  effective-config identity; uses bounded no-follow snapshots with detailed
  diffs; supervises the process; and accepts externally classified write
  observation. It always leaves the operator verdict pending.
- Universal Setup owns read-only package verification, and FacMan routes its
  package-verification command through that pinned provider.
- Diagnostic export now combines bounded traversal with stable no-follow
  handle reads, a reviewed-format allowlist, fail-closed structured redaction,
  pseudonymous source identity, production archive output, transaction
  recovery, and post-commit self-verification. The exact-SHA Linux,
  Windows/package, macOS archive, AppKit, schema, and security matrix is green.
- The explicit Linux x64 CLI package-preview profile passed its zero-skip
  Ubuntu 24.04 target proof at revision
  `93edfdc59865e4a07f261bdabb61c6e2db6d0f99`. ELF, glibc, dependency,
  extraction, relocation, read-only-root, and pathless runtime evidence is
  schema-valid and the unsigned artifact digest is revision-pinned.
- Run and recovery locks now retain a platform handle, record stable file
  identity, revalidate the path before exact-object deletion, reject links and
  substitutions, and conservatively refuse unreviewed shared filesystems. This
  is a supported local-filesystem claim only.
- Selected package builds now emit a hash-closed SPDX 2.3 SBOM and adjacent
  artifact provenance binding source state, provider pins, workspace/component
  manifests, toolchain, CI identity, timestamp policy, and final digest.
  Publisher authenticity remains unproven because the evidence is unsigned.

## Current Goal

The ordered R3.3 core through `FACMAN-R3.3-PROOF-CLOSEOUT-01` is frozen and
green. The baseline, archive dependency, production
core, local mod/modset routes, save/portable-transfer routes, bounded workspace
transaction recovery, reviewed diagnostic export, and Linux target package
proof are frozen at green exact-SHA checkpoints. Continue with
`FACMAN-LOCAL-FILESYSTEM-LOCK-HARDEN-03` on supported local filesystems only.
That local lock proof is now exact-SHA cross-platform green. Continue with
`FACMAN-SBOM-AND-PROVENANCE-01`, keeping provenance distinct from publisher
authenticity. That unsigned provenance proof is now exact-SHA target-CI green.
The macOS Intel CLI package lane is exact-SHA target-CI green with path-free
Mach-O, deployment, integrity, relocation, SPDX, and provenance evidence.
R3.3 core and Stretches A-C are frozen in the stretch closeout checkpoint.
The next authority gate is the operator-only real Factorio isolation smoke.
Keep `run.execute` and real Factorio isolation human-gated; do not schedule Windows discovery again.
The ordered authority remains `.aide/memory/r3.3-workunits.md`.

## Quarantined Capabilities

- Real `run.execute` remains unavailable until the prepared operator-supplied
  Factorio isolation smoke receives a reviewed human pass.
- Native GUI diagnostic export UX remains deferred; the enabled authoritative
  operation is exposed through the CLI and doctor CLI alias only.
- Setup mutation, networking, credentials, dynamic plugins, and release
  publication remain deferred.

## Root Truth

- `include/` is public ABI only.
- `runtime/` is private compiled implementation.
- `apps/` contains frontend entrypoints and presentation shells.
- `content/` contains declarative Factorio content and policy.
- `contracts/` contains compatibility law, including but not limited to schema.
- `release/` contains packaging and release definitions.
- `docs/`, `tests/`, `tools/`, `cmake/`, and `external/` retain their named
  responsibilities.
- `source/`, `src/`, `data/`, `schemas/`, and `packaging/` are retired roots.

Production packages must not bundle Factorio binaries, credentials, AIDE, or a
Python runtime.
