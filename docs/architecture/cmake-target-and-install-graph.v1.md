# CMake target and install graph v1

The root build now composes module-owned `CMakeLists.txt` files. Runtime, binding,
client, CLI, and native-test targets are defined beside their source rather than
in one root target registry. Stable namespaced aliases expose the architectural
surface from `facman::core` through `facman::cli`; historical concrete target
names remain available to existing automation.

First-party targets consume four interface policies: warnings, hardening,
sanitizers, and coverage. Canonical `FACMAN_*` options control products and proof
instrumentation. The former `FLAUNCH_*` switches remain synchronized compatibility
aliases during migration.

Install rules expose explicit Runtime, CLI, Contracts, Content, Documentation,
Licenses, and Development components and install a machine-readable artifact
manifest. The experimental Development component exports a relocatable
`FacMan::flb` shared-library target, complete FLB and ULK headers, CMake and
pkg-config discovery metadata, and ABI dependency metadata. A CTest installs,
relocates, builds, and runs current- and older-header C consumers. Presets cover
development hosts, debug/release CI, sanitizers, coverage, and the three current
x64 package lanes.

Package artifact lookup is deterministic. It checks documented configuration
and dependency output directories and never recursively searches a build tree,
so stale binaries cannot win by traversal order. WorkUnit 12 will make the
install tree itself the package staging input.

`tools/cmake_architecture_check.py` enforces module composition, aliases,
policies, options, install components, presets, and deterministic lookup.
