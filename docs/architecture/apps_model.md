# Apps Model

`apps/` is organized by frontend class:

```text
cli/
tui/
daemon/
gui/
```

GUI providers are nested under `apps/gui/`:

```text
windows/
  winforms/
  winui/
macos/
  appkit/
  swiftui/
linux/
  gtk/
  qt/
```

OS-first GUI folders are intentional. The project has multiple frontend stacks
per operating system, so the path records both the platform and the toolkit.

Distribution packages should expose only the terminal and GUI access proved
for that lane. `facman` deliberately combines normative CLI JSON, bounded human
CLI, and explicit TUI modes over independently testable modules. Native GUI
executables remain separate. The daemon directory currently reserves ownership
but provides no supported transport. A GUI is not the CLI, and no renderer is
the backend for another.

There is no Python frontend root. Python may support repository automation and
tests, but FacMan runtime entrypoints are native app shells.
