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

Validate the contract with:

```powershell
py -3 tools/frontend_contract_check.py
```
