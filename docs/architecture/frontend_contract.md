# Frontend Contract

Every FacMan frontend is a view over the same command graph. The CLI, TUI,
daemon host, WinForms, WinUI, AppKit, SwiftUI, GTK, and Qt lanes must account
for the same command IDs before the GUI shells grow real screens.

The contract lives at:

```text
contracts/command/frontend/frontend.required_commands.v1.toml
```

It separates command parity from implementation readiness. Each frontend must
declare one status for every required and deferred command:

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
run.preview
diagnostics.export
```

## Deferred Commands

```text
run.execute
modsets.lock
saves.backup
export.instance
import.instance
setup.preview
```

Deferred commands may already exist in the CLI, but GUI parity does not require
them in the first shell milestone. The next safe GUI work is WinForms and
AppKit showing required commands as implemented or structured refusals over the
same command client.

## WinForms Shell Milestone

`FACMAN-WINFORMS-SHELL-01` is the first GUI shell that moves required commands
from placeholder status to a concrete frontend surface. The implementation is
still deliberately thin:

- command behavior is reached through the command-client path, not implemented
  in C#;
- screens collect only the arguments needed by existing command IDs;
- raw backend output is rendered as command results instead of reinterpreted as
  GUI-owned state;
- deferred commands are visible only as disabled/refused items with structured
  reasons;
- setup mutation, Mod Portal network behavior, server execution, developer
  execution, discovery logic, modset resolution, save backup/export, and import
  implementation remain outside the WinForms lane.

This means `windows.winforms` may declare required command IDs as
`implemented` in the frontend contract when the shell can invoke those command
IDs through the shared client and render the returned success, error, or
refusal payload. It does not mean WinForms owns the backend behavior, stores
credentials, launches Factorio directly, or replaces CLI/TUI/daemon parity.

## AppKit Shell Milestone

`FACMAN-APPKIT-SHELL-01` applies the same proof to the first macOS native GUI
lane. The AppKit shell should match WinForms for command/result/refusal parity,
not visual parity. It may use Objective-C or Objective-C++ to call the same
command-client path, render the required command IDs, and keep deferred command
IDs disabled or refused with reasons.

The AppKit lane has the same ownership boundary as WinForms: no Factorio
discovery logic, no setup mutation, no Mod Portal network behavior, no server or
developer execution, no modset resolver, no save/export/import implementation,
and no credentials in the frontend.

Validate the contract with:

```powershell
py -3 tools/frontend_contract_check.py
py -3 tools/frontend_parity_check.py
```
