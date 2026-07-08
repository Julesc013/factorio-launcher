# Coding Standards

## C ABI

- every public struct has `struct_size`
- every public function returns an explicit result code
- all output pointers are validated
- ownership transfer appears in the function name or documentation
- public strings are `(data, size)` pairs
- no public ABI function stores caller-owned pointers past the call unless the
  lifetime is documented

## C and C++

- keep C89 compatibility in public headers
- keep C++ behind C wrappers
- no exceptions across ABI boundaries
- no STL types in public headers
- isolate platform code under `platform/<target>/`
- use small files organized by behavior, not vague utility buckets

## Schemas

- all command payloads are schema-versioned
- dry-run responses use the same schema shape as execute responses
- secret-bearing fields must be marked and redacted in diagnostics

## Frontends

- frontends do not own product logic
- frontends do not mutate install state directly
- frontends must support dry-run previews for destructive actions
- CLI, TUI, WinForms, AppKit, GTK, and Qt all call the same command graph
