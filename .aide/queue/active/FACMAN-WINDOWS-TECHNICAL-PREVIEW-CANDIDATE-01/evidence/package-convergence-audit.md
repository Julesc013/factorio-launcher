# Canonical package convergence audit

The package machinery currently proves two different halves of the candidate:

- the legacy WinForms builder emits deterministic SBOM, provenance, licence,
  package-manifest, and runtime-verifier material, but its producer is explicitly
  provisional because the resolution root is not embedded and round-trip
  verified;
- the canonical `windows_winforms_technical_preview_x64` v2 target resolves,
  stages, and verifies the static provider graph, but has no production archive
  command binding that verified stage to one distributable artifact.

Therefore no single current artifact satisfies the full candidate claim. The P0
repair is convergence, not a new package architecture: archive the verified
canonical v2 stage deterministically, preserve its exact resolution and stage
digests, verify the written archive, refuse output clobbering, and prove
cross-root byte determinism. Legacy assurance outputs can then be bound to that
canonical artifact in a later bounded slice.

Three independent compiled-root builds, exact-candidate environment smokes,
human accessibility, and a tagless release-bundle driver remain subsequent
qualification work. No tag, signature, publication, or public support claim is
authorized.
