# Canonical package convergence audit

The package machinery currently proves two different halves of the candidate:

- the legacy WinForms builder emits deterministic SBOM, provenance, licence,
  package-manifest, and runtime-verifier material, but its producer is explicitly
  provisional because the resolution root is not embedded and round-trip
  verified;
- the canonical `windows_winforms_technical_preview_x64` v2 target resolves,
  stages, and verifies the static provider graph, but has no production archive
  command binding that verified stage to one distributable artifact.

The integrated repair now archives the verified canonical v2 stage
deterministically, preserves its exact resolution and stage digests, verifies
the written archive, refuses output clobbering, and proves cross-root byte
determinism. The production assurance commands recompute deterministic SPDX and
provenance sidecars from that verified artifact and bind exact source, provider,
dependency-lock, staged-licence, runtime-resolution, inventory, and container
identities under closed release authority.

The package seam is therefore converged in code, but it is not yet an admitted
native candidate. A release-eligible exact build-source observation, actual
native runtime-verifier run, three independent compiled-root builds,
exact-candidate environment smokes, human accessibility, and a complete tagless
release bundle remain subsequent qualification work. No tag, signature,
publication, or public support claim is authorized.
