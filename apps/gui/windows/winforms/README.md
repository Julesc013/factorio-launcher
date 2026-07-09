# Windows WinForms GUI Frontend

Target .NET Framework 4.8 and keep Windows 7 SP1 compatibility best-effort.
The GUI is a command graph client. It must not own install mutation, mod
resolution, or launch-plan generation.

This is the legacy Windows GUI lane. Modern Windows UI work belongs in
`apps/gui/windows/winui/`.

## FACMAN-WINFORMS-SHELL-01

The first WinForms shell is intentionally narrow. It presents the required
frontend command surface through tabs for:

- Dashboard
- Doctor
- Installs
- Instances
- Launch Plan
- Diagnostics
- Settings/About

The shell uses a thin command client over the shared command graph. It can route
required commands through the configured `facman` CLI JSON executable and render
the returned stdout, stderr, exit code, or structured refusal. It does not
discover Factorio installs in C#, resolve modsets in C#, store credentials,
download from the Mod Portal, mutate setup-managed installs, execute servers,
run developer tools, or launch Factorio directly.

Deferred commands remain visible in the command catalog as disabled/refused
items with reasons:

- `run.execute`
- `modsets.lock`
- `saves.backup`
- `export.instance`
- `import.instance`
- `setup.preview`

Use the Settings/About screen to point the shell at a built `facman` executable
and an optional workspace. If no executable is configured or discoverable, the
shell returns a frontend refusal instead of inventing GUI behavior.
