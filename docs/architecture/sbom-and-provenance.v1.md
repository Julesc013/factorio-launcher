# SBOM and Unsigned Provenance v1

Every selected built package contains `manifest/sbom.spdx.v2.3.json`. The SPDX
2.3 document is included before component and hash-manifest generation, so the
ordinary package integrity closure covers it.

The document describes FacMan, every high-level component copied from the
CMake install tree, and the pinned Universal Launcher, Universal Setup, Miniz,
and PicoJSON dependencies. `CONTAINS` relationships close the installed
component set; independent verification reconstructs that set from the
installed bundle manifest and rejects a missing package or relationship.
FacMan, Universal Launcher, Universal Setup, and Miniz have MIT license
records, and PicoJSON has a BSD-2-Clause record. Built contracts and Factorio
content declare MIT. The Universal license values are accepted only at the
pinned revisions whose exact license-file digests are recorded in the lock.

First-party source headers are managed by `tools/apply_spdx_headers.py`, and
`REUSE.toml` records generated and third-party trees. Packages carry the exact
vendored Miniz and PicoJSON notices as `licenses/Miniz.txt` and
`licenses/PicoJSON.txt`. Packages also carry exact Universal Launcher and
Universal Setup MIT notices. Their contents and all recorded license digests
are machine-checked. The operator decision is recorded separately and does not
imply signing, publication, or publisher authenticity.

## Artifact binding

After archive creation, FacMan writes an adjacent
`<artifact>.provenance.v1.json`. It records and verifies:

- final artifact name, size, and SHA-256;
- FacMan, Universal Launcher, and Universal Setup revisions;
- clean/dirty source-tree state and a deterministic source-state SHA-256;
- workspace-lock path and digest;
- component, hash-manifest, and SPDX paths and digests;
- target build toolchain identity;
- GitHub Actions run, attempt, workflow, repository, and source SHA, or an
  explicit local/non-CI identity;
- the source commit UTC timestamp and `source_commit_utc` timestamp policy.

The source-state digest hashes the binary Git diff plus every untracked,
non-ignored source path and its bytes. A clean tree therefore has a stable
empty-state digest; a local dirty proof cannot masquerade as the committed
revision alone.

## Reproducibility and trust boundary

The creation timestamp comes from the pinned source commit, not wall-clock
build time. Toolchain and CI identities are evidence inputs and are checked
against the package build information. Mutation proof covers the artifact,
workspace lock, component and hash manifests, SBOM, source identity, and CI
identity.

The result says `provenance_recorded` and
`publisher_authenticity_not_proven`. It is unsigned, unpublished, and not a
SLSA attestation, transparency-log entry, or trusted publisher signature. An
attacker able to replace both the artifact and adjacent JSON can forge both;
authenticity requires a separate signing and trust-distribution authority.
