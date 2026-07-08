# Apps Model

`apps/` is organized by frontend class:

```text
cli/
tui/
daemon/
gui/
python_cli/
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
