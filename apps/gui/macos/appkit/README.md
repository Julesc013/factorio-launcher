# macOS AppKit C1 preview

This is the native AppKit projection of backend-derived FacMan C1 state through
the existing bounded process RPC. Deterministic fixtures remain only behind
explicit `FACMAN_PRESENTATION_MODE=evidence`. It targets x86_64 and macOS
10.13 or later. It is a preview lane: the
source and bundle prototype do not claim live Play, signed/notarized packaging,
runtime qualification, or stable support.

The primary product shell contains Instances, Installations, Activity, and
Settings/About plus a persistent selected-instance Launch Deck. Advanced keeps
the generated command explorer. Native AppKit controls, the application and
Navigate menus, Command-1 through Command-5, default-button operation, and
explicit accessibility labels cover keyboard and assistive-technology paths.
System Native is the safe default; FacMan OEM+ changes only the Launch Deck and
Command-0 restores System Native immediately.

The explicitly labelled evidence controls demonstrate selection/create, readiness, exact
`stale_readiness` refusal before effects, backend-owned running/exited state,
Last Run, relaunch with a distinct operation ID, and interruption/recovery.
They start no Factorio process. Advanced commands use the existing bounded
`rpc --stdio` process client, including independent pipe draining, timeout,
output budgets, structured refusal, and honest `outcome_unknown` handling.

Build the bundle on macOS:

```sh
FACMAN_APPKIT_BUILD_ROOT=/absolute/external/facman-appkit-build
cmake -S apps/gui/macos/appkit -B "$FACMAN_APPKIT_BUILD_ROOT" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=x86_64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=10.13
cmake --build "$FACMAN_APPKIT_BUILD_ROOT" --config Release
```

The result is the actual `FacMan.app` prototype surface defined by
the generated `Info.plist`. Its public bundle identifier is
`io.github.julesc013.facman`, and its semantic and bundle versions come from
`release/index/version.v2.toml`. Experimental remains a support tier, not part
of the public identity. A configured or bundled `facman` executable remains required for
Advanced RPC commands. The shell adds no discovery, setup mutation, direct
client, daemon, runtime route, transport rewrite, or Universal Launcher ABI.
