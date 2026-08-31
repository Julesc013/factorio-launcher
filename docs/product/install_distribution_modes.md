# Install And Distribution Modes

FacMan uses one command graph in portable and installed layouts. Placement and
maintenance authority differ; command semantics do not.

## Alpha.3 modes

| Platform | Portable | Setup default | Setup effects |
| --- | --- | --- | --- |
| Windows x64 | extract ZIP anywhere | current user, no elevation | versioned generation, Start Menu entry, HKCU uninstall/repair registration, receipts |
| macOS Intel x64 | extract ZIP and run/copy `FacMan.app` | system application layout | `/Applications/FacMan.app`, `/usr/local/bin/facman`, native package receipt |
| Linux x64 | extract tar.zst anywhere | current user | `~/.local/opt/facman`, `~/.local/bin` links, desktop entry, installed-state and receipts |

All setup packages are self-contained and offline. Windows and Linux support
install, verify, repair, and uninstall through their maintenance entrypoints.
The macOS alpha uses the native PKG receipt and includes removal guidance; a
full graphical maintenance application remains later work.

Windows does not add anything to `PATH` by default. `FacMan.exe` and
`facman.exe` cannot share one directory because their names differ only by
case on a case-insensitive filesystem. A future optional PATH integration must
be explicit and reversible.

## Invariants

- Portable packages create no shortcuts, registrations, services, or managed
  installation state.
- Setup never downloads a second payload and does not install or modify
  Factorio.
- Uninstall removes only setup-owned product and integration paths and
  preserves FacMan workspaces and Factorio data.
- No automatic updater, system service, file association, or real-Factorio
  execution authority is admitted in alpha.3.
- Unsigned private-alpha packages remain manual-test candidates, not supported
  public releases.

## Product and Factorio ownership

Installing FacMan is distinct from managing a Factorio installation. Universal
Setup owns admitted FacMan setup transactions. Universal Launcher owns runnable
product orchestration. FacMan owns Factorio-specific interpretation and refuses
unauthorized mutation. Foreign Factorio installations remain read-only unless
a later, explicit adoption workflow grants authority.

The workspace is independent of the application install. Instance data,
modsets, saves, diagnostics, and audit records must survive FacMan repair and
uninstall.
