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
```

Reusable launcher behavior belongs in `runtime/` or the sibling universal
repositories. GUI providers must render command graph behavior; they must not
own Factorio discovery, mod resolution, launch-plan generation, or setup
mutation.

Python product frontends are intentionally not present. Python belongs in
repo-local tools, validators, fixtures, and tests when useful.
