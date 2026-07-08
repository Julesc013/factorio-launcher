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

C89 is not a performance claim. It is an ABI discipline: fewer runtime
assumptions, easier bindings, and predictable binary boundaries.

