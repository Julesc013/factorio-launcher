# Install Discovery

The first discovery implementation is read-only.

Commands:

```bash
facman installs scan [--path <root>] [--json]
facman installs list
facman installs inspect <install-id> [--json]
facman installs import <path> --id <install-id> [--json]
```

Ownership classifications:

- `managed`: universal setup owns mutation
- `foreign`: Steam, installer, or package manager owns it
- `imported`: user selected folder, mutation disabled
- `portable`: user-controlled portable tree

No repair or uninstall is allowed for foreign-owned installs.

## Implemented Native Slice

`installs scan` is read-only. It inspects explicit `--path` roots, optional
`;`-separated `FACMAN_DISCOVERY_ROOTS`, and conservative platform defaults. It
reports candidate install refs but does not register them. Registration remains
an explicit `installs import` action.

The native scanner recognizes:

- manually selected standalone folders
- Steam library layouts under `steamapps/common/Factorio`
- portable folders
- headless folders
- macOS `.app` bundles
- invalid folders, reported with `verification.status = invalid`

All discovered refs report `safe_actions.repair = false` and
`safe_actions.uninstall = false`.
