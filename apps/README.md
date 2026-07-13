# Apps

Thin executable and frontend shells live here:

```text
apps/
  cli/
  tui/
  daemon/
  gui/
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

Reusable launcher behavior belongs in `runtime/` or the sibling universal
repositories. GUI providers must render command graph behavior; they must not
own Factorio discovery, mod resolution, launch-plan generation, or setup
mutation.

Packages may ship proven CLI, TUI, and GUI binaries side by side. The daemon
placeholder is excluded from product claims until a real protocol and lifecycle
are implemented and runtime-tested. Individual executables do not multiplex
every frontend role; the GUI is not the CLI, and the CLI is not the backend for
the GUI.

Python product frontends are intentionally not present. Python belongs in
repo-local tools, validators, fixtures, and tests when useful.
