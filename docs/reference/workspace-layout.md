# Workspace Layout

FacMan is one repository in a three-repo ecosystem. The Universal repositories
must stay separate, but their local checkout paths should not require source
edits.

Provider consumption is explicit:

```text
FACMAN_PROVIDER_MODE=source
FACMAN_PROVIDER_MODE=installed_static
FACMAN_PROVIDER_MODE=installed_shared
```

Source mode requires exact
`FLAUNCH_UNIVERSAL_SETUP_ROOT` and
`FLAUNCH_UNIVERSAL_LAUNCHER_ROOT` CMake cache values (or those exact
per-provider environment variables). It does not search shared roots,
`external/`, or nearby sibling directories. Each checkout must match the
selected provider lock exactly.

Installed modes require exact
`FACMAN_UNIVERSAL_SETUP_SDK_ROOT` and
`FACMAN_UNIVERSAL_LAUNCHER_SDK_ROOT` prefixes plus their exact
`FACMAN_UNIVERSAL_*_IDENTITY_FILE` observations. Package discovery is
restricted to those prefixes. A missing or partial SDK never falls back to a
source checkout or a globally installed runtime.

For a layout like:

```text
D:/Projects/Factorio/factorio-launcher
D:/Projects/Universal/universal-setup
D:/Projects/Universal/universal-launcher
```

generate the exact local CMake arguments rather than relying on the physical
layout:

```bash
py -3 tools/workspace_config.py doctor
py -3 tools/workspace_config.py cmake-args
py -3 tools/workspace_config.py write-cmake-user-presets
```

`CMakeUserPresets.json` is intentionally ignored by Git. It is machine-local
state, not project truth.

Canonical pre-adoption conformance may pass an out-of-tree
`facman.provider_conformance_lock.v1` with
`FACMAN_PROVIDER_CONFORMANCE_ONLY=ON`. That lock is non-release-eligible,
records every authority as false, and does not change the tracked workspace
pins. Normal builds cannot override the tracked provider lock.

Cross-repo validation has two modes:

```bash
py -3 tools/cross_repo_check.py --product-only
py -3 tools/cross_repo_check.py
```

Use product-only mode for single-repo clones. Use full mode when both Universal
repositories are checked out.

For fresh-clone or branch handoff proof, run the reproducibility smoke:

```bash
py -3 tools/repro_workspace_smoke.py
py -3 tools/repro_workspace_smoke.py --build
```

The smoke supports both flat workspaces and grouped `Factorio/` + `Universal/`
workspaces, including the layout:

```text
D:/Projects/Factorio/factorio-launcher
D:/Projects/Universal/universal-setup
D:/Projects/Universal/universal-launcher
```
