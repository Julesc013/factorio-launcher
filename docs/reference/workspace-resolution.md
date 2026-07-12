# Workspace Resolution

FacMan resolves a workspace once in the native client layer. CLI and TUI call
that resolver directly. Desktop clients may submit an explicit workspace; an
empty value delegates to the CLI transport and therefore uses the same law.

The precedence is:

1. explicit `--workspace` or transport workspace;
2. `FACMAN_WORKSPACE`;
3. the compatibility alias `FACTORIO_LAUNCHER_WORKSPACE`;
4. an existing real directory at `~/.facman/workspace`;
5. `<platform data>/facman/workspace`.

The legacy path is never moved automatically. A legacy link, reparse point, or
non-directory refuses with `workspace_legacy_unsafe`. If no explicit value or
safe platform user path exists, resolution refuses with
`workspace_default_unavailable`; FacMan does not fall back to the current
directory.

The platform-native defaults are under Roaming AppData on Windows,
`XDG_DATA_HOME` (or `~/.local/share`) on Linux, and Application Support on
macOS. Resolution does not create the selected workspace.
