# Windows WinForms GUI Frontend

Target .NET Framework 4.8 and keep Windows 7 SP1 compatibility best-effort.
The GUI is a command graph client. It must not own install mutation, mod
resolution, or launch-plan generation.

This is the legacy Windows GUI lane. Modern Windows UI work belongs in
`apps/gui/windows/winui/`.

## FACMAN-WINFORMS-SHELL-01

The shell presents its primary workflows through tabs for:

- Dashboard
- Doctor
- Installs
- Instances
- Launch Plan
- Diagnostics
- Settings/About

The shell uses the generated C# command catalog and generic request mapper over
the shared command graph. It can route backend-live commands through the
configured `facman` stdio machine transport and render
the returned stdout, stderr, exit code, or structured refusal. It does not
discover Factorio installs in C#, resolve modsets in C#, store credentials,
download from the Mod Portal, mutate setup-managed installs, execute servers,
run developer tools, or launch Factorio directly.

Unavailable commands remain visible with generated availability, refusal,
risk, and effect metadata. `run.execute` remains human-gated.

Use the Settings/About screen to point the shell at a built `facman` executable
and an optional workspace. If no executable is configured or discoverable, the
shell returns a frontend refusal instead of inventing GUI behavior.
