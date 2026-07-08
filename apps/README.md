# Apps

Thin executable and frontend shells live here:

```text
apps/
  cli/
  tui/
  daemon/
  gui/
    win32/
    appkit/
    gtk/
    qt/
  python_cli/
```

Reusable launcher behavior belongs in `runtime/` or the sibling universal
repositories. GUI providers must render command graph behavior; they must not
own Factorio discovery, mod resolution, launch-plan generation, or setup
mutation.
