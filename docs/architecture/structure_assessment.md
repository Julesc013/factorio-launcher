# Structure Assessment

## Current Assessment

The first bootstrap proved the idea quickly but mixed two futures:

- a Python package under a generic source root
- long-term native ABI and platform frontend plans

That was useful for a runnable v0.1, but it was not the right final shape.

The repo now uses ownership-oriented top-level roots instead of lifecycle
accidents. The top-level directory name should tell a maintainer what kind of
contract they are entering:

```text
include/   public ABI
src/       private native implementation
apps/      frontend executables and shells
data/      product-owned manifests, templates, and policy
schemas/   wire/storage compatibility contracts
launcher/  current Python prototype
docs/      architecture, product, platform, and planning records
tests/     unit, integration, contract, golden, and fixture coverage
tools/     repo automation
cmake/     native build policy
```

This is more future-proof than a generic `source/` root because the repo has
several kinds of source with different compatibility promises. Public ABI
headers, private native internals, frontend apps, product data, and prototype
Python code should not share one directory contract.

## Problems Fixed Now

- `src/` was renamed to `launcher/` for the current Python prototype.
- redundant `factorio_launcher/factorio/...` Python nesting was flattened.
- Factorio product config moved from root `product/` to `data/factorio/`.
- schemas moved into versioned namespaces under `schemas/common`, `schemas/usk`,
  `schemas/ulk`, and `schemas/factorio`.
- native roots now use `include/`, `src/`, and `apps/`.
- GUI roots now live under `apps/winforms`, `apps/appkit`, `apps/gtk`, and
  `apps/qt`.
- native executable scaffolds now use explicit app names:
  `apps/factorio_cli`, `apps/factorio_tui`, and `apps/factorio_daemon`.
- public ABI headers now use `usk_`, `ulk_`, and `flb_` prefixes instead of a
  vague universal `ul_` prefix.
- Python prototype integration adapters now use `integrations/usk` and
  `integrations/ulk` so the bridge layer matches the native vocabulary.

## Target Shape

The target repository shape is:

```text
include/
  usk/      C89 public ABI for setup mutation
  ulk/      C89 public ABI for launcher orchestration
  flb/      C ABI for the Factorio product binding

src/
  base/     C89 portable primitives
  platform/ common, windows, posix, macos, linux adapters
  usk/      setup kernel internals
  ulk/      launcher kernel internals and command graph
  factorio/ Factorio binding internals

apps/
  factorio_cli/
  factorio_tui/
  factorio_daemon/
  winforms/
  appkit/
  gtk/
  qt/

data/factorio/
  product/
  discovery/
  launch_templates/
  instance_templates/
  policy/

schemas/
  common/
  usk/
  ulk/
  factorio/
```

This layout supports forks and optional frontends cleanly. A fork can replace
`apps/gtk` without touching `src/ulk`; a product binding can add new
`data/<product>` and `src/<product>` areas without rewriting the setup kernel;
a downstream packager can include CLI-only artifacts without carrying GUI
toolkit dependencies.

## Function and ABI Conventions

Public C functions use:

```text
<prefix>_<module>_<verb>_v<abi-version>
```

Examples:

```text
usk_install_verify_v1
ulk_command_execute_v1
ulk_launch_plan_build_v1
flb_command_execute_v1
flb_discovery_scan_v1
```

Public structs use the same prefix and carry `struct_size` so callers and
callees can detect version drift. Public headers expose no C++ classes,
templates, exceptions, STL types, RTTI, or ownership ambiguity.

Private code can use stronger internal language features where they fit:
C++98 for universal cleanup/state helpers and C++11 for Factorio-specific
complexity. That freedom stops at the C ABI boundary.

## File Naming Conventions

- C and C++ implementation files use `snake_case`.
- Public headers use `prefix_module.h`, such as `ulk_command.h`.
- C# WinForms files keep `PascalCase.cs`.
- AppKit files keep Objective-C/AppKit conventions:
  `MainWindowController.m`, `CommandClient.mm`.
- JSON schemas use `name.v1.schema.json` inside a namespace directory.
- TOML templates use `snake_case.toml`.
- Platform directories use full names: `windows`, `macos`, `linux`, `posix`.

Do not revive old names such as `win32`, `commandclient.cpp`,
`launch-templates`, `instance-templates`, or unversioned schema names.

## Frontend Rule

No frontend is foundational to another frontend. The CLI may be the first and
best-tested frontend, but the CLI, TUI, WinForms, AppKit, GTK, and Qt shells
must all call the same command graph, daemon protocol, or direct C ABI.

The forbidden shape is:

```text
GUI -> TUI -> CLI -> core
```

The accepted shape is:

```text
frontends -> command graph / daemon / C ABI -> product binding
```

GUI-only install logic, mod resolution, launch-plan generation, or hidden
repair behavior is an architecture bug.

## Optimal Next Refactor

The best long-term reorganization is:

1. Build a real C command graph library under `src/ulk/command`.
2. Port the Python command handlers into native command handlers.
3. Keep CLI JSON output stable while changing internals.
4. Introduce `flb_command_execute_v1` behind the public binding ABI.
5. Make the Python package a test/prototype harness or delete it after parity.
6. Split universal setup and universal launcher back into separate repos when
   the Factorio vertical slice proves the API pressure.

The migration should be boring and contract-first:

1. Freeze command names and schema IDs.
2. Add native command handlers behind the current CLI JSON behavior.
3. Keep Python tests as golden behavior checks while native code grows.
4. Move state mutation behind USK handoff points only when dry-run and audit
   records exist.
5. Add daemon mode for long operations after command payloads are stable.
6. Add GUI frontends only as views over the command graph.

## Naming Standards

- public C symbols: `ulk_` for universal launcher, `usk_` for universal setup,
  `flb_` for Factorio binding
- public headers: `snake_case.h`
- C/C++ source files: `snake_case.c`, `snake_case.cpp`
- C# types: `PascalCase.cs`
- Objective-C files: `PascalCase.m`, Objective-C++ bridge files `PascalCase.mm`
- schemas: `name.v1.schema.json` inside `schemas/common`, `schemas/usk`,
  `schemas/ulk`, or `schemas/factorio`
- commands: dotted lowercase names, such as `instances.create`

## Performance Standard

Use JSON-RPC or CLI subprocesses only at command granularity. Never call the
backend once per file, mod edge, or progress tick. Long-running operations
belong in the daemon with progress events and cancellation.

## Backportability Standard

Keep legacy support pressure isolated:

- public ABI remains C89-style C
- Windows native code uses `windows`, not version-specific root names
- Windows 7 support notes live in platform docs and build policy
- macOS deployment target notes live in platform docs and build policy
- Linux GUI toolkit decisions stay under `apps/`, never inside core
- no GUI toolkit dependency enters `src/base`, `src/usk`, `src/ulk`, or
  `src/factorio`

The project should still build a headless CLI/daemon profile on systems with no
GUI stack installed.
