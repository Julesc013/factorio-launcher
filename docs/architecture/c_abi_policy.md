# ABI Policy

The public ABI is C89-style C. It is the compatibility contract between the
universal setup kernel, universal launcher kernel, product bindings, native
frontends, GUI wrappers, daemon clients, and test harnesses.

Rules:

- expose C ABI only
- expose no C++ classes, STL types, exceptions, RTTI, or templates
- put size and version fields on public structs
- make ownership transfer explicit
- return explicit result codes
- use configured typedefs instead of assuming compiler-specific widths
- keep allocator, error, logging, and string lifetime policy visible
- query an owning ABI and each required dependency ABI separately
- accept only the same major and a non-newer minor unless a versioned contract
  declares a stricter compatibility rule

C89 is not a performance claim. It is an ABI discipline: fewer runtime
assumptions, easier bindings, and predictable binary boundaries.
