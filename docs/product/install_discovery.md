# Install Discovery

The first discovery implementation is read-only.

Commands:

```bash
facman installs scan
facman installs list
facman installs inspect <install-id>
facman installs import <path>
```

Ownership classifications:

- `managed`: universal setup owns mutation
- `foreign`: Steam, installer, or package manager owns it
- `imported`: user selected folder, mutation disabled
- `portable`: user-controlled portable tree

No repair or uninstall is allowed for foreign-owned installs.
