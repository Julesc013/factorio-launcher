# Future Layers Plan

The durable structure is stable enough that the next work should add contract
depth and product capability rather than another root redesign.

Permanent boundary:

```text
Universal Setup mutates installed software state.
Universal Launcher orchestrates runnable product state.
FacMan interprets Factorio-specific facts.
Frontends present commands and reports.
Contracts preserve compatibility.
Validators prevent regression.
```

## Implemented In This Spine

- command effects and risk tiers
- refusal code registry
- workspace schemas and workspace invariant check
- package contract catalog and portable CLI/TUI manifests
- UI strings, themes, and accessibility check
- credential/redaction policy contract
- frontend parity surface check

## Next Work Units

### R2.2 Capability And Refusal Depth

- emit registered refusal codes from runtime paths
- attach effect/risk metadata to command graph inspection
- display effect/risk tiers in CLI/TUI/GUI reports

### R2.3 Workspace And Package Proof

- materialize package-smoke layouts from package manifests
- add instance-root fixture tests
- add export/import redaction and portability roundtrips

### R2.4 Runtime Client Ownership

- extract generic JSON, daemon, C ABI, result, refusal, and progress clients
  into Universal Launcher
- keep FacMan-specific wrappers in `factorio-launcher/runtime/client/`
- keep Factorio result shaping in the Factorio binding

### R2.5 Local Modset Correctness

- parse local mod ZIP `info.json`
- parse dependencies and incompatibilities
- verify hashes
- score reproducibility deterministically

### R2.6 Diagnostic Intelligence

- `facman doctor --explain`
- `facman launch plan <instance> --why`
- `facman modsets verify --explain`
- export portability report
- Steam and foreign-owned safety report

### R3 Safe Beta

- diagnostic bundles
- save backup/export/import hardening
- package layout tests
- redaction tests
- frontend runtime smokes over fake backend JSON

### R4 Universal Setup MVP

- install-local
- verify
- uninstall managed-only
- audit
- transaction journal
- rollback proof

### R5 Managed Factorio Setup

- local archive install through Universal Setup
- managed install verification
- foreign-owned read-only registration
- Steam mutation refusal
- portable install adoption flow

### R6 Deferred Network And Execution

- Mod Portal read-only search
- authenticated download through credential store
- server preview and execute
- developer tool preview and execute

### R7 Modern GUI Lanes

- GTK shell
- WinUI shell
- SwiftUI shell
- Qt shell
- localization, theme, accessibility consumption in each frontend

## Strict Rule

```text
contracts first
runtime second
frontend third
automation fourth
intelligence last
```

No future layer may bypass the command graph or turn a frontend into backend
behavior.
