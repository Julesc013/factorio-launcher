# Structure Assessment

## Current Assessment

The first bootstrap proved the idea quickly but mixed two futures:

- a Python package under a generic source root
- long-term native ABI and platform frontend plans

That was useful for a runnable v0.1, but it was not the right final shape.

## Problems Fixed Now

- `src/` was renamed to `launcher/` for the current Python prototype.
- redundant `factorio_launcher/factorio/...` Python nesting was flattened.
- Factorio product config moved from root `product/` to `factorio/product/`.
- Factorio schemas moved from root `schemas/` to `factorio/schemas/`.
- root `schemas/` is now reserved for shared command/request/response schemas.
- native roots were added for `universal/`, `factorio/`, `cli/`, `tui`,
  `daemon/`, and `gui/`.

## Optimal Next Refactor

The best long-term reorganization is:

1. Build a real C command graph library under `universal/`.
2. Port the Python command handlers into native command handlers.
3. Keep CLI JSON output stable while changing internals.
4. Introduce `factorio_binding_execute_v1` behind the public binding ABI.
5. Make the Python package a test/prototype harness or delete it after parity.
6. Split universal setup and universal launcher back into separate repos when
   the Factorio vertical slice proves the API pressure.

## Naming Standards

- public C symbols: `ul_` for universal launcher, `us_` for universal setup,
  `fb_` for Factorio binding
- public headers: `snake_case.h`
- C/C++ source files: `snake_case.c`, `snake_case.cpp`
- C# types: `PascalCase.cs`
- Objective-C files: `PascalCase.m`, Objective-C++ bridge files `PascalCase.mm`
- schemas: `<domain>-<record>.schema.json` for shared records,
  `factorio-<record>.schema.json` for Factorio records
- commands: dotted lowercase names, such as `instances.create`

## Performance Standard

Use JSON-RPC or CLI subprocesses only at command granularity. Never call the
backend once per file, mod edge, or progress tick. Long-running operations
belong in the daemon with progress events and cancellation.

