# Native GUI Readiness

Native GUI providers exist under:

- `apps/gui/win32`
- `apps/gui/appkit`
- `apps/gui/gtk`
- `apps/gui/qt`

The GUI phase is readiness, not GUI-only product behavior. Each provider must
remain a command client over the FacMan command graph, daemon, JSON mode, or C
ABI. Product discovery, setup mutation, mod resolution, save import/export, and
server execution remain backend responsibilities.

`tools/gui_surface_check.py` validates that each provider has a command-client
surface and does not contain direct process execution or setup/mod-portal
mutation markers.

This keeps the frontend architecture:

```text
CLI / TUI / Win32 / AppKit / GTK / Qt
  -> command graph / daemon / C ABI
  -> universal launcher
  -> Factorio binding
  -> universal setup only for managed install mutation
```
