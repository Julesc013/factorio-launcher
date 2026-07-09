# Workspace Layout

FacMan is one repository in a three-repo ecosystem. The Universal repositories
must stay separate, but their local checkout paths should not require source
edits.

Supported local discovery order:

1. Explicit roots:
   `FLAUNCH_UNIVERSAL_SETUP_ROOT` and `FLAUNCH_UNIVERSAL_LAUNCHER_ROOT`
2. Shared roots:
   `FLAUNCH_UNIVERSAL_ROOT` and `FLAUNCH_WORKSPACE_ROOT`
3. Pinned local checkouts:
   `external/universal-setup` and `external/universal-launcher`
4. Nearby workspace layouts:
   `../universal-*`, `../../Universal/universal-*`, and parent workspace
   variants

For a layout like:

```text
D:/Projects/Factorio/factorio-launcher
D:/Projects/Universal/universal-setup
D:/Projects/Universal/universal-launcher
```

the locator should find the Universal repos without extra arguments. If a
machine uses another layout, set one of the supported environment variables or
generate local CMake arguments:

```bash
py -3 tools/workspace_config.py doctor
py -3 tools/workspace_config.py cmake-args
py -3 tools/workspace_config.py write-cmake-user-presets
```

`CMakeUserPresets.json` is intentionally ignored by Git. It is machine-local
state, not project truth.

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
