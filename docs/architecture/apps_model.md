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
win32/
appkit/
gtk/
qt/
```

`apps/gui/win32` may use WinForms for the Windows 7 SP1 best-effort lane, but
the architecture name stays provider-oriented.

There is no Python frontend root. Python may support repository automation and
tests, but FacMan runtime entrypoints are native app shells.
