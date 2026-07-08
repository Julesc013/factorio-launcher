# Language Policy

## Tier 0: Public ABI

Use C89-style C for cross-project and cross-language APIs:

- universal setup public API
- universal launcher public API
- product-binding ABI
- plugin ABI
- GUI/native-core interop ABI
- diagnostic/reporting ABI
- allocator/error/logging ABI

## Tier 1: Universal Internals

Use C89 for handles, result systems, portable strings, filesystem/process
abstractions, audit events, command graph records, and manifest streams.

C++98 may be used internally for RAII cleanup, state machines, small internal
containers, builders, and tests. It must stay behind `extern "C"` wrappers.

## Tier 2: Factorio Binding

C11/C++11 are allowed internally for Factorio-specific complexity:

- mod dependency resolution
- Mod Portal cache and indexing
- version comparison
- save and modset scanning
- server/RCON helpers
- diagnostic bundling

The Factorio binding still exposes only C ABI outward.

## Frontends

- CLI and TUI: native frontends over the command graph
- Windows GUI: .NET Framework 4.8 WinForms
- macOS GUI: AppKit Objective-C/Objective-C++
- Linux GUI: GTK first, Qt optional
