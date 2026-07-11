# Changed Files

- `contracts/schema/release/`: strict SPDX 2.3 subset and unsigned build
  provenance contracts.
- `tools/provenance_build.py`: package SBOM generation, artifact provenance,
  source-state/CI identity, digest binding, and verifier.
- `tools/package_build.py` and runtime smoke: SBOM before hash closure,
  source-derived timestamp/toolchain identity, adjacent provenance after
  archive creation, and required layout.
- `release/index/dependency_lock.v1.toml`: explicit MIT or `NOASSERTION`
  license truth for every bundled component.
- Linux CI: preserve adjacent provenance with the tarball and package proof.
- Tests/checkers/docs/AIDE: mutation proof, strict enforcement, architecture,
  roadmap, claims, and bounded evidence.

No signature, publishing workflow, provider source, runtime command, ABI, setup
mutation, or network behavior changed.
