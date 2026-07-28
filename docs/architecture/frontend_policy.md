# GUI Frontend Policy

No frontend is the foundation for another frontend.

Do not build:

```text
WinForms GUI -> TUI -> CLI -> core
```

Build:

```text
Universal Setup Kernel        C89 public ABI, C/C++ internal
Universal Launcher Kernel     C89 public ABI, C/C++ internal
        |
Universal Command Graph       schemas, dry-run, audit, errors
        |
Factorio Product Binding      C ABI outward, native C/C++ internally
        |
CLI / TUI / WinForms / WinUI / AppKit / SwiftUI / GTK / Qt frontends
```

The CLI is the first frontend because it is scriptable and easy to test. It is
not the long-term foundation of the GUI. GUIs may initially use bounded process
JSON as a compatibility transport, then move to the frontend-neutral direct
client. A persistent local service is justified only by operation-lifetime or
multi-client evidence.

Every frontend must account for the same stable command graph and normalized
outcomes. Primary GUI journeys use hand-designed native views backed by shared
semantic snapshots and actions; generated command forms remain an Advanced,
diagnostic, administrative, and compatibility surface. GUI-only domain or
authority behavior is a product bug.

Native shells prefer the frontend-neutral direct client. Process RPC is a
compatibility and diagnostic fallback. A persistent local service is introduced
only when evidence proves operations must survive frontend death or serve
multiple clients; it is not a default architectural symmetry.

Each distribution package may include proven CLI, TUI, and GUI binaries. A
daemon is included only after its own qualification. Each executable remains a
distinct frontend shell.

Command parity is locked in
[frontend_contract.md](frontend_contract.md). New frontend work should update
that contract before adding GUI-specific screens.

Portable semantics, HIG authority, classic and modern shell profiles, System
Native/OEM+ appearance, theme safety, accessibility, performance, and recovery
are governed by
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).
