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

Distribution packages should expose CLI, TUI, daemon, and GUI access where that
lane supports them. Individual executables should not combine all modes. A GUI
executable presents commands; it is not the CLI, and the CLI is not the backend
for the GUI.

There is no Python frontend root. Python may support repository automation and
tests, but FacMan runtime entrypoints are native app shells.
