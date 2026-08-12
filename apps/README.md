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

The terminal product converges on one `facman` executable that multiplexes CLI
JSON, bounded human CLI, and explicit `facman tui` modes over shared frontend
libraries. Native GUI binaries remain separate platform adapters. The daemon
placeholder is excluded from product claims until a measured lifecycle need,
threat model, protocol, compatibility TCK, and recovery proof are admitted.
The GUI is not the CLI, and neither renderer is the backend for another.

Python product frontends are intentionally not present. Python belongs in
repo-local tools, validators, fixtures, and tests when useful.
