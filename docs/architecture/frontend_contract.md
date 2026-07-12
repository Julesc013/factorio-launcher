# Frontend Contract

Every FacMan frontend is a view over the same command graph. The CLI, TUI,
daemon host, WinForms, WinUI, AppKit, SwiftUI, GTK, and Qt lanes must account
for the same command IDs before the GUI shells grow real screens.

The contract lives at:

```text
contracts/command/frontend/frontend.required_commands.v1.toml
```

It separates command parity from implementation readiness. Commands are
classified as required frontend parity, optional frontend exposure, or
authoritatively unavailable. Each frontend declares one status for every
command:

```text
implemented
stubbed_with_refusal
not_supported_with_reason
```

`implemented` means the frontend can reach the shared backend command surface.
`stubbed_with_refusal` means the command is visible but intentionally refuses
with a structured reason. `not_supported_with_reason` means the lane is not
yet expected to expose that command.

Command parity is not the same as build, runtime, or package readiness. The
frontend proof ladder lives in
[`docs/quality/frontend_proof_levels.md`](../quality/frontend_proof_levels.md).

## Required Commands

```text
help
version
doctor
product.inspect
command_graph.inspect
installs.scan
installs.import
installs.inspect
instances.list
instances.create
launch_plan.build
launch_plan.preflight
run.preview
```

Frontend IDs need not be registry IDs. The generated record's `runtime_id` is
the canonical value passed to Universal Launcher after parser normalization;
for example `instances.list` maps to `instance.list`. `diagnostics.export`
maps to its own runtime route and requires generated `instance_id` and
`output_path` fields; it is not the read-only `diagnostics.run` report route.

## Generated Native Catalogs

`tools/codegen/generate_metadata.py` emits the catalog consumed by each native
frontend:

```text
apps/gui/windows/winforms/GeneratedCommandCatalog.cs
apps/gui/macos/appkit/FacManGeneratedCommandCatalog.h
apps/gui/macos/appkit/FacManGeneratedCommandCatalog.m
apps/tui/generated_command_catalog.hpp
```

Each record carries contract/runtime identity, category, localization keys,
availability and refusal reason, risk/effects, CLI grammar, typed request-field
mapping, repeatability/default metadata, and renderer identity. WinForms and
AppKit keep stable adapter names, but those adapters contain no command list or
per-command payload switch. Adding a registered contract therefore does not
require a catalog edit in any of those frontends.

## Optional Commands

```text
diagnostics.export
mods.import
modsets.lock
modsets.verify
modsets.export
saves.list
saves.backup
saves.clone
instance.export
instance.import
workspace.recovery.inspect
workspace.recovery.plan
workspace.recovery.apply
```

Optional commands are implemented by the CLI, TUI, WinForms, and AppKit command
surfaces. This is a frontend exposure classification, not a weaker backend
availability or proof claim.

## Unavailable Commands

```text
run.execute
setup.preview
```

Unavailable commands stay on authoritative refusal routes. Their presence in
the catalog must never be read as implementation or promotion.

## WinForms Shell Milestone

`FACMAN-DESKTOP-FRONTEND-PARITY-02` moves required and optional non-execution
commands to a generated concrete WinForms surface. The implementation remains
deliberately thin:

- command behavior is reached through the command-client path, not implemented
  in C#;
- generic forms collect arguments from generated field descriptors;
- raw backend output is rendered as command results instead of reinterpreted as
  GUI-owned state;
- unavailable commands are visible only as disabled/refused items with
  structured reasons;
- setup mutation, Mod Portal network behavior, server execution, developer
  execution, discovery logic, modset resolution, save backup/export, and import
  implementation remain outside the WinForms lane.

This means `windows.winforms` may declare required command IDs as
`implemented` in the frontend contract when the shell can invoke those command
IDs through the shared client and render the returned success, error, or
refusal payload. It does not mean WinForms owns the backend behavior, stores
credentials, launches Factorio directly, or replaces CLI/TUI/daemon parity.

## AppKit Shell Milestone

`FACMAN-DESKTOP-FRONTEND-PARITY-02` applies the same proof to the macOS native
GUI lane. The AppKit shell matches WinForms for generated command/result/refusal
parity, not visual parity. Objective-C and Objective-C++ call the same bounded
command-client path, build request forms from generated descriptors, support
cancellation, and keep unavailable command IDs disabled or refused with
reasons.

The AppKit lane has the same ownership boundary as WinForms: no Factorio
discovery logic, no setup mutation, no Mod Portal network behavior, no server or
developer execution, no modset resolver, no save/export/import implementation,
and no credentials in the frontend.

Validate the contract with:

```powershell
py -3 tools/frontend_contract_check.py
py -3 tools/frontend_parity_check.py
```
