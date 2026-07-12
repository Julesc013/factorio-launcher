# macOS AppKit Frontend

Use Objective-C/AppKit with Objective-C++ only for bridge code. Keep the legacy
lane buildable with a toolchain that supports `MACOSX_DEPLOYMENT_TARGET=10.13`.
Implementation files live under `apps/gui/macos/appkit/`.

## FACMAN-APPKIT-SHELL-01

The AppKit shell mirrors the WinForms proof at the command/result/refusal
level. It is not a visual parity target.

Required screens:

- Dashboard
- Doctor
- Installs
- Instances
- Launch Plan
- Diagnostics
- Settings/About

The generated command palette and category tabs expose every implemented
required and optional non-execution workflow. Request forms are built from the
generated field descriptors, including paths, booleans, defaults, and
repeatable values; no per-command input map remains in Objective-C.

Commands and payload fields come from `FacManGeneratedCommandCatalog`; the
Objective-C++ command client contains no hand-maintained catalog or argument
switch. Backend-live commands route through the shared bounded stdio transport,
while unavailable commands remain visible with generated reasons. The AppKit
transport supports cancellation, bounded output, and timeouts. The AppKit
claim remains compile-only until an actual bundle runtime proof exists.

The AppKit shell must not own Factorio discovery, setup mutation, Mod Portal
network behavior, server or developer execution, modset resolution, save
backup/export/import behavior, credential storage, or direct Factorio launch
behavior.
