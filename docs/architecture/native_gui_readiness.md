# Native GUI Readiness

Native GUI providers exist under:

- `apps/gui/windows/winforms`
- `apps/gui/windows/winui`
- `apps/gui/macos/appkit`
- `apps/gui/macos/swiftui`
- `apps/gui/linux/gtk`
- `apps/gui/linux/qt`

The GUI phase is readiness, not GUI-only product behavior. Each provider must
remain a command client over the FacMan command graph, daemon, JSON mode, or C
ABI. Product discovery, setup mutation, mod resolution, save import/export, and
server execution remain backend responsibilities.

`tools/gui_surface_check.py` validates that each provider has a command-client
surface and does not contain direct process execution or setup/mod-portal
mutation markers.

This keeps the frontend architecture:

```text
CLI / TUI / WinForms / WinUI / AppKit / SwiftUI / GTK / Qt
  -> command graph / daemon / C ABI
  -> universal launcher
  -> Factorio binding
  -> universal setup only for managed install mutation
```
