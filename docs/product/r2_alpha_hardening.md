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
  accessibility, package, package-layout, GUI, language/runtime, command,
  frontend, alpha-golden, refusal, discovery, and release-readiness checks.

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

## Next R2 Work Units

1. `FACMAN-DISCOVERY-FIXTURES-02`
   - Add more platform install fixtures.
   - Prove scan remains read-only across portable, Steam, headless, macOS app,
     invalid, and adopted/imported layouts.

2. `FACMAN-MODZIP-DEPTH-02`
   - Expand local ZIP metadata fixtures.
   - Cover dependency operators, optional dependencies, incompatibilities,
     missing `info.json`, and malformed archives.

3. `FACMAN-SAVE-ROUNDTRIP-02`
   - Strengthen backup, clone, export, and import roundtrips with multiple
     saves and existing-target refusal behavior.

4. `FACMAN-DIAGNOSTIC-REDACTION-02`
   - Route diagnostic bundle assembly through the redaction policy.
   - Add tests that secrets do not appear in diagnostics, exports, or logs.

5. `FACMAN-PACKAGE-SKELETON-02`
   - Materialize fixture package layouts without building real installers.
   - Validate required binaries, libraries, contracts, content, licenses,
     frontend manifest, package manifest, and support matrix placement.

## Still Deferred

- Real Mod Portal network behavior.
- Universal Setup mutation.
- Server/dev execution.
- Auto-update.
- Signed installers and real package publication.
- WinUI, SwiftUI, GTK, and Qt implementation.
- AI recommendation or opaque automation behavior.
