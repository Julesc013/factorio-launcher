# Adding a package profile

Create a target-specific `release/profiles/<id>/profile.toml`. Declare the
runner, architecture, deployment or libc baseline, allowed system dependencies,
package format, components, and publication state. Do not use an OS-neutral
name for a platform-specific proof.

The package must stage only through `cmake --install`. Add install components
in module-local CMake, update manifest/layout contracts, and keep release
artifact discovery deterministic. Archive metadata follows
`docs/architecture/reproducible-package-pipeline.v1.md`.

Add layout, runtime relocation, read-only-root, integrity, provenance, and
independent-build digest proofs. Dirty proof packages are forbidden; developer
output requires explicit `--allow-dirty`. Signing and publisher authenticity
remain separate promotion gates.
