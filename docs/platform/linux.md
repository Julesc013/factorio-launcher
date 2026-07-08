# Linux GUI Policy

Linux target order:

1. CLI
2. TUI
3. GTK frontend
4. Qt frontend only if there is a clear reason

GTK is the first Linux GUI because it matches the C ABI style and is available
on GNU/Linux and Unix, Windows, and Mac OS X. Prefer GTK 3 for broad legacy
distro compatibility unless the project intentionally raises the baseline.

Qt is optional. It should exist only if the richer C++ desktop app path
justifies the extra packaging and maintenance surface.

The core must not depend on a GUI toolkit. The launcher must still work on a
server with no GUI packages installed.
