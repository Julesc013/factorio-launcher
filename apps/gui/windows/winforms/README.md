# Windows WinForms C1 frontend

This is the supported C1 reference presentation for Windows 10/11 x64. It
targets .NET Framework 4.8, uses native Windows controls and System Native
appearance, declares Per-Monitor V2 DPI awareness, and remains a thin frontend.
It must not own install mutation, mod resolution, launch-plan generation, or
live Play authority. Production state is backend-derived over the existing
bounded process RPC; the backend must enable and admit exact `run.execute`.

`C1ShellForm` is the product entrypoint. It exposes Instances, Installations,
Activity, and Settings/About as the four player-facing pages, with a persistent
Launch Deck. The deterministic `facman.presentation.v0` fixtures are embedded
only for explicit `FACMAN_PRESENTATION_MODE=evidence` review of readiness,
exact `stale_readiness` refusal, running,
ordinary exit, Last Run, relaunch, interruption, and recovery can be reviewed
without a live process route. Live mode never uses them as production state.

## Advanced command explorer

The previous generated command surface remains available only from Advanced.
It retains category tabs for:

- Dashboard
- Doctor
- Installs
- Instances
- Launch Plan
- Diagnostics
- Mods
- Saves
- Recovery
- Capabilities
- Settings/About

The shell uses the generated C# command catalog and generic request mapper over
the shared command graph. It can route backend-live commands through the
configured `facman` stdio machine transport and render
the returned stdout, stderr, exit code, or structured refusal. It does not
discover Factorio installs in C#, resolve modsets in C#, store credentials,
download from the Mod Portal, mutate setup-managed installs, execute servers,
run developer tools, or launch Factorio directly.

Request forms are generated at runtime from the catalog field descriptors,
including paths, booleans, defaults, and repeatable values. The shell has no
per-command argument switch. Long-running backend requests can be cancelled;
transport timeout and output limits remain enforced by the shared client.

Unavailable commands remain visible with generated availability, refusal,
risk, and effect metadata. `run.execute` remains human-gated.

Advanced opens the explorer's Settings/About screen to select a built `facman`
executable and optional workspace. If no executable is configured or
discoverable, it returns a frontend refusal instead of inventing GUI behavior.

## Prototype and checks

Build and validate the shell with:

```powershell
dotnet msbuild apps\gui\windows\winforms\FacMan.WinForms.csproj /t:Rebuild /p:Configuration=Debug /p:Platform=x64
python tools\facman_winforms_c1_check.py
python tools\winforms_c1_runtime_smoke.py
python tools\build_winforms_c1_portable.py
```

The ZIP is an unsigned, unpublished fixture prototype. Its embedded Play path
starts no Factorio process and changes no qualified runtime identity. The
bounded process client is retained for generated Advanced commands.
