# macOS AppKit Frontend

Use Objective-C/AppKit with Objective-C++ only for bridge code. Keep the legacy
lane buildable with a toolchain that supports `MACOSX_DEPLOYMENT_TARGET=10.13`.
Implementation files live under `apps/gui/macos/appkit/`.

## FACMAN-APPKIT-SHELL-01

The first AppKit shell mirrors the WinForms proof at the command/result/refusal
level. It is not a visual parity target yet.

Required screens:

- Dashboard
- Doctor
- Installs
- Instances
- Launch Plan
- Diagnostics
- Settings/About

Required commands route through the shared command-client path and render the
returned output. Deferred commands remain visible only as disabled/refused
states with reasons:

- `run.execute`
- `modsets.lock`
- `saves.backup`
- `export.instance`
- `import.instance`
- `setup.preview`

The AppKit shell must not own Factorio discovery, setup mutation, Mod Portal
network behavior, server or developer execution, modset resolution, save
backup/export/import behavior, credential storage, or direct Factorio launch
behavior.
