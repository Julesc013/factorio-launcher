# Language Policy

FacMan's primary implementation languages are C, C++, C#, Objective-C, and
Objective-C++. Python is allowed where it is conventional and useful for
repository automation, validators, generators, fixtures, and tests, but it is
not a product runtime language for FacMan packages.

## Tier 0: Public ABI

Use a C-compatible, C89-callable public ABI style for cross-project and
cross-language APIs:

- universal setup public API
- universal launcher public API
- product-binding ABI
- plugin ABI
- GUI/native-core interop ABI
- diagnostic/reporting ABI
- allocator/error/logging ABI

The ABI discipline matters more than the internal implementation language:
public structs are plain data with size/version fields, ownership transfer is
explicit, errors are explicit result codes, and no public header exposes C++
classes, STL, exceptions, RTTI, templates, or compiler-specific layout
assumptions.

## Tier 1: Universal Internals

The legacy portable lane keeps C89/C++98-compatible ABI discipline for handles,
result systems, portable strings, filesystem/process abstractions, audit events,
command graph records, and manifest streams.

Mainline private implementation may use newer C/C++ dialects only when the
supported toolchain floor permits it and the public ABI remains stable. C++98
remains acceptable for universal cleanup wrappers, state machines, small
containers, builders, and tests. Any C++ implementation must stay behind
`extern "C"` wrappers.

## Tier 2: Factorio Binding

C/C++ are the primary implementation languages for Factorio-specific
complexity:

- mod dependency resolution
- Mod Portal cache and indexing
- version comparison
- save and modset scanning
- server/RCON helpers
- diagnostic bundling

The Factorio binding still exposes only C ABI outward.

When a modern toolchain lane is introduced, Factorio-specific private code may
move beyond C11/C++11 before the public ABI does. Do not let old ABI constraints
freeze private implementation forever, and do not let newer private
implementation leak through DLL/shared-library boundaries.

## Frontends

- CLI and TUI: native C/C++ frontends over the command graph
- Windows GUI: WinForms legacy lane and WinUI modern lane
- macOS GUI: AppKit legacy lane and SwiftUI modern lane
- Linux GUI: GTK X11 lane and Qt Wayland lane

Toolkit-required language/runtime floors are isolated to their frontend
folders. See
[language_and_runtime_policy.md](language_and_runtime_policy.md) for the
enforced root-level policy.

## Tooling And Scripts

Python remains appropriate for repo-local tooling:

- validators and policy checks
- schema checks
- fixture generation
- AIDE Lite helpers
- test harness glue
- one-off migration scripts

Python must not provide `facman`, `factorio-launcher`, GUI, daemon, or TUI
runtime entrypoints. The product runtime must build from the native app shells
and native libraries.
