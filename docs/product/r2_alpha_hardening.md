# R2 Alpha Hardening

R2 is the local power-user alpha lane. It should deepen the existing CLI/runtime
product path instead of adding new frontends, network behavior, setup mutation,
server execution, or GUI-only workflows.

## Current Proof

- Native CLI/TUI/daemon build through CMake.
- WinForms and AppKit shell proofs compile in remote CI.
- Required frontend command coverage is validated mechanically.
- Command effects, refusal codes, workspace contracts, package contracts,
  accessibility/theme contracts, and redaction policy are present.
- `strict_check.py` runs structure, schema, security, source-format,
  accessibility, package, package-layout, package-manifest, package-skeleton,
  GUI, language/runtime, command, frontend, alpha-golden, refusal, discovery,
  and release-readiness checks.

## Hardened In This Slice

- New install imports write metadata to `installs/refs/`.
- Legacy `installs/installed_state/` install refs remain readable but are no
  longer created for new workspaces.
- Workspace initialization creates `workspace.v1.json`, canonical workspace
  roots, `installs/refs/`, `installs/setup_state_refs/`, and `exports/`.
- Instance creation is covered by invariant tests for config, mods, saves,
  scenarios, script-output, logs, crash, locks, and cache directories.
- Portable instance export redacts obvious secret-bearing `config.ini` values.
- Package layout smoke validation expands `base_manifest` inheritance and
  checks relative destinations, entrypoints, duplicate destinations, and
  required contracts/content placement.
- Distribution contracts define first release profiles for Windows WinForms,
  macOS AppKit, Linux X11 GTK, portable CLI, and portable TUI lanes.
- Package manifest validation checks release profiles, support metadata,
  frontend manifests, install modes, required package paths, license files,
  forbidden payload markers, and CLI/TUI-only GUI toolkit isolation.
- Package skeleton validation materializes fixture trees for Windows WinForms,
  macOS AppKit, Linux GTK, portable CLI, and portable TUI without real
  installers, signing, publication, or built package artifacts.
- Discovery fixture validation scans deterministic fake Factorio install roots
  for Windows Steam, Windows standalone, Windows portable, macOS app bundle,
  Linux tarball, Linux headless, Linux OS-package-owned, imported/adoptable,
  and invalid layouts.
- Discovery goldens pin source, ownership, platform, capability, path-kind,
  validation, refusal, and setup-mutation fields without depending on host
  Factorio state.
- Read-only invariant tests prove scan, import, doctor, and foreign-owned
  repair/uninstall refusal do not mutate fixture install trees.
- Local mod ZIP fixtures cover simple metadata, required dependencies,
  optional and hidden-optional dependencies, incompatibilities, Factorio
  version pins, missing `info.json`, malformed `info.json`, invalid filenames,
  duplicate versions, and explicit incompatibility pairs.
- Local mod ZIP import validates metadata before copying into an instance and
  returns structured refusals for unsafe or unsupported ZIPs.
- Modset lockfiles pin SHA-1, SHA-256, source, enabled state, Factorio version,
  and structured dependency/incompatibility declarations.
- Modset lock/export refuse duplicate versions, unsatisfied dependencies,
  incompatible pairs, invalid mod ZIPs, and incompatible Factorio versions.
- Modset verification reports SHA-1 and SHA-256 drift with a structured
  `mod_hash_mismatch` refusal.
- Mod ZIP tests prove source fixture ZIPs are not mutated, invalid imports do
  not partially install, and exported modsets avoid secrets and absolute
  machine-local paths.
- Save fixtures cover valid saves, mod-metadata-adjacent saves, existing
  targets, duplicate file-name ordering, malformed archives, and
  secret-adjacent config.
- Save backup writes a sidecar manifest with source, destination, timestamp,
  SHA-1, and SHA-256 metadata.
- Save backup, save clone, instance export, and instance import refuse existing
  targets instead of overwriting silently.
- Save backup, clone, and export refuse malformed save ZIPs before writing
  outputs.
- Instance import preflights archive safety and target existence before writing
  the restored instance tree.
- Save roundtrip tests prove source fixtures are not mutated and instance
  exports redact config secrets and avoid machine-local workspace paths.
- Diagnostic redaction policy contracts define field-name, path-name,
  key-value, pattern, binary-file, archive-file, and allowed-metadata behavior.
- Runtime diagnostics redaction replaces credential-like values with
  `[FACMAN_REDACTED]` and emits structured redaction events.
- The R2 fixture suite assembled diagnostic bundles and excluded the known
  secret corpus, denied paths, binary files, and archive-like inputs.
- A later adversarial review showed that this did not prove multiline
  structured redaction or bounded no-follow traversal. Diagnostic and
  doctor-bundle export are now quarantined pending that stronger proof.
- Diagnostic tests prove redaction is deterministic and idempotent, binary
  files are skipped, archive-like files are excluded, and source fixtures are
  not mutated.

## Next R2 Work Units

1. `FACMAN-DISCOVERY-FIXTURES-02`
   - Done for fixture-backed read-only discovery and ownership classification.
   - Still not real Steam VDF parsing, Windows registry scan, macOS Spotlight
     scan, Linux package-manager scan, or managed install adoption.

2. `FACMAN-MODZIP-DEPTH-02`
   - Done for deterministic local ZIP fixtures, metadata parsing, structured
     dependency and incompatibility parsing, SHA-1/SHA-256 lock entries,
     invalid ZIP refusals, duplicate-version refusals, and read-only source
     artifact invariants.
   - Still not Mod Portal networking, downloaded release selection, compressed
     production archive compatibility, dependency solving from remote metadata,
     or account/token behavior.

3. `FACMAN-SAVE-ROUNDTRIP-02`
   - Done for deterministic save fixtures, backup manifests, clone/import
     roundtrip, malformed-save refusals, existing-target refusals, redacted
     exports, and source-fixture non-mutation.
   - Still not deep Factorio save introspection, Steam Cloud mutation, map
     preview, benchmark save execution, or save-associated modset inference.

4. `FACMAN-DIAGNOSTIC-REDACTION-02`
   - Done for redaction policy contracts, known-corpus runtime redaction,
     deterministic/idempotent text handling, and multiline JSON string-field
     redaction.
   - Diagnostic bundle and doctor-bundle assembly are quarantined after the
     adversarial safety review; their former fixture proof is retained as
     historical evidence only.
   - Still not Factorio account login, credential-store implementation,
     Mod Portal token handling, diagnostic upload, or GUI diagnostic UX.

5. `FACMAN-PACKAGE-SKELETON-02`
   - Done for contract-backed fixture layouts.
   - Still not a real installer, signed artifact, notarized app, AppImage, DMG,
     or published package.

## Still Deferred

- Real Mod Portal network behavior.
- Universal Setup mutation.
- Server/dev execution.
- Auto-update.
- Signed installers and real package publication.
- WinUI, SwiftUI, GTK, and Qt implementation.
- AI recommendation or opaque automation behavior.
