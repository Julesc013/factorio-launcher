# Install Modes

FacMan has one release semantics model with three install modes.

## Portable

Portable mode means:

```text
no admin required
no system registration required
state may live beside the app or in a selected workspace
verification can run in place
removal can be deleting the folder
```

Portable mode is the first mode to prove because it shows that FacMan does not
depend on global Universal Launcher or Universal Setup installation.

## User Installed

User-installed mode means:

```text
no admin required
installed under a user-owned app path
per-user shortcuts or app entries
per-user installed state
per-user update, repair, and uninstall
```

User install is the default target for most users because it avoids elevation
and avoids shared system state.

## System Installed

System-installed mode means:

```text
admin or root required
shared executable install
per-user workspaces remain separate
updates require elevation
uninstall removes only setup-owned files
```

System install owns the application. It does not own the user's Factorio
worlds, saves, accounts, modsets, instances, or workspaces.

## Workspace Preservation

Uninstalling FacMan must preserve user workspaces unless the user explicitly
chooses a destructive workspace removal action. This rule is machine-checked by
`tools/validators/release/check_install_modes.py` and
`tools/validators/release/check_no_workspace_in_system_package.py`.
