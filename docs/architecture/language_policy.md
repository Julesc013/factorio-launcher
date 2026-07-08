# Language Policy

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

C11/C++11 are allowed internally for Factorio-specific complexity:

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

- CLI and TUI: native frontends over the command graph
- Windows GUI: .NET Framework 4.8 WinForms
- macOS GUI: AppKit Objective-C/Objective-C++
- Linux GUI: GTK first, Qt optional
