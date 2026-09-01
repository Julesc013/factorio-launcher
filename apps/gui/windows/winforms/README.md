# Windows WinForms C1 frontend

This is the supported C1 reference presentation for Windows 10/11 x64. It
targets .NET Framework 4.8, uses native Windows controls and System Native
appearance, declares Per-Monitor V2 DPI awareness, and remains a thin frontend.
It must not own install mutation, mod resolution, launch-plan generation, or
live Play authority. Production state is backend-derived over the existing
bounded process RPC; the backend must enable and admit exact `run.execute`.

`C1ShellForm` is the product entrypoint. It exposes Instances, Installations,
Content, Saves, Activity, and Settings/About as the six player-facing pages,
with Advanced kept separate and a persistent Launch Deck. The deterministic
`facman.presentation.v0` fixtures are embedded
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
the shared client enforces exact raw-byte limits of 1 MiB for requests, 16 MiB
for stdout, and 64 KiB for stderr within one 30-second operation deadline. Two
seconds of that deadline are reserved for complete process-tree cleanup.

The client accepts success only from strict UTF-8, one closed JSON response,
and exact schema, protocol, request, command, operation, and attempt identity
matches. Before dispatch, local failure remains a no-effects refusal. Once a
request write begins, timeout, cancellation, exhausted output, I/O failure,
early exit, malformed output, or an identity mismatch is `outcome_unknown`,
says effects may have occurred, and requires
`workspace.recovery.inspect`. Missing backend fields are never synthesized.

On Windows the backend is created suspended without a shell, assigned to a
kill-on-close Job Object before resume, and not considered cleaned up until the
complete contained tree is empty and both output channels are drained. Backend
selection and package identity remain the separate
`FACMAN-C1-BACKEND-IDENTITY-01` WorkUnit.

Unavailable commands remain visible with generated availability, refusal,
risk, and effect metadata. `run.execute` remains human-gated.

Advanced opens the explorer's Settings/About screen to select a built `facman`
executable and optional workspace. If no executable is configured or
discoverable, it returns a frontend refusal instead of inventing GUI behavior.

## Prototype and checks

Assembly, file, informational, and manifest versions are generated from
`release/index/version.v2.toml`; the project remains .NET Framework 4.8 x64.
Build into the marker-owned external development root and validate with:

```powershell
py -3 tools\dev.py build product
py -3 tools\facman_winforms_c1_check.py
py -3 tools\winforms_c1_runtime_smoke.py
py -3 tools\winforms_transport_hardening_check.py
```

The ZIP is an unsigned, unpublished fixture prototype. Its embedded Play path
starts no Factorio process and changes no qualified runtime identity. The
bounded process client is retained for generated Advanced commands.
