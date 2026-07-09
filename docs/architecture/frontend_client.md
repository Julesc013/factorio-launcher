# Frontend Command Client

Every frontend talks to the same command graph. No frontend is the backend for
another frontend.

The frontend-neutral client layer lives under `runtime/client/` and supports:

- CLI JSON command invocation
- daemon JSON-RPC
- direct C ABI calls

WinForms, WinUI, AppKit, SwiftUI, GTK, Qt, TUI, and CLI shells can choose the
transport that fits their platform maturity, but they must not invent hidden
behavior outside the command graph.

The direct C ABI transport has an implemented execution seam:

```text
fl_command_client_execute_cabi_v1(...)
```

It calls the Factorio binding and, through that binding, reaches the universal
launcher command graph for product-neutral commands.
