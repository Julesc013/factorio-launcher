# Runtime

Owns private compiled implementation for FacMan's Factorio product binding,
runtime package lookup, command clients, and platform adapters.

May contain:

- C and C++ implementation behind stable C ABI boundaries
- Factorio product-binding modules
- runtime package/component location and verification
- frontend-neutral command clients
- low-level platform adapters

Must not contain:

- public ABI headers for other repositories
- frontend presentation code that belongs under `apps/`
- release packaging recipes
- user data, downloaded Factorio binaries, or credentials
- language-version buckets such as `c11/` or `cpp11/`

Folders are domain boundaries. Language standards are build properties, not
architecture folders.
