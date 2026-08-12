# Linux GUI Policy

Linux target order:

1. CLI
2. same-binary TUI
3. GTK X11 frontend
4. optional, separately admitted Qt 6 Widgets frontend
5. optional, separately admitted Qt 6 Quick Controls/Kirigami Wayland frontend

GTK is the first Linux GUI because it matches the C ABI style and is available
on GNU/Linux and Unix, Windows, and Mac OS X. Prefer GTK 3 for broad legacy
distro compatibility unless the project intentionally raises the baseline.

GTK is the required initial Linux GUI for `1.0`. Qt 6 Widgets and Qt Quick
Controls with Kirigami are optional later lanes. If both are admitted, their
shell implementations remain isolated. Neither Qt projection may raise the
language/runtime requirement of the backend, CLI, TUI, daemon, or universal
repos.

The core must not depend on a GUI toolkit. The launcher must still work on a
server with no GUI packages installed.

GTK 3 uses a traditional cross-desktop shell by default; a GNOME-oriented
header-bar profile may be added but is not mandatory. GTK CSS remains narrowly
scoped to FacMan product surfaces. Qt Widgets uses native styles, palettes, and
platform conventions. Kirigami uses semantic theme colors, units,
layouts, and KDE icon roles. Raw CSS, QSS, or QML is not a user-theme format.
See [`docs/product/interface_design_system.md`](../product/interface_design_system.md).
