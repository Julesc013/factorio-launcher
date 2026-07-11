# External Dependencies

Early development may pin sibling repositories here:

```text
external/universal-setup/
external/universal-launcher/
```

These should be submodules or reproducible pinned checkouts, not copied source
that silently forks the universal projects.

Reviewed source-vendored runtime dependencies are also isolated here. Their
exact pins, source hashes, licenses, notices, SBOM records, and runtime-network
properties are authoritative in `release/index/dependency_lock.v1.toml`.

The build and cross-repo validators search these paths before walking nearby
workspace parents. Machine-specific absolute paths still belong in environment
variables or ignored local CMake user presets, not in committed source.
