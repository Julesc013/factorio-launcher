# Architecture

FacMan is the Factorio-facing product binding and app shell for a future
universal launcher ecosystem.

```text
Universal Setup Kernel        C89 public ABI, C/C++ internal
Universal Launcher Kernel     C89 public ABI, C/C++ internal
        |
Universal Command Graph       stable command model, schemas, dry-run, audit
        |
Factorio Product Binding      C ABI outward, native C/C++ internally
        |
CLI / TUI / WinForms / WinUI / AppKit / SwiftUI / GTK / Qt frontends
```

The CLI is the first frontend and may expose JSON for early GUI integration,
but it is not the foundation of the GUI. The intended command direction is:

```text
frontend -> Universal Launcher router -> registered Factorio binding
         -> FacMan application operation -> typed result -> frontend renderer
```

JSON is a compatibility and process boundary. Native application operations
use typed requests and results. Every frontend ultimately calls the same
authoritative command handlers.

The universal launcher should understand artifact sets, launch plans,
instances, profiles, and diagnostics. It should not understand Factorio mods.

The frozen macro-decisions and bounded correction programme are defined in
[architecture_freeze.md](architecture_freeze.md) and
[../quality/safety_proof_gates.md](../quality/safety_proof_gates.md).
