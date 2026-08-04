# Changed-file evidence

The working tree implements the release-resolution work in these cohesive areas:

- `tools/release_compiler/` and `tools/facman_release.py`: deterministic compilation, canonical outputs, explanation/diff, staging, inspection, and package verification.
- `release/index/*.v2.toml`, compatibility/trust/channel inputs, and `release/toolchain.lock`: authored product, target, provider, support, artifact, and toolchain truth.
- `contracts/schema/release/`: the authored model, ten resolved records, stage manifest, and package inspection schemas.
- `tools/release_resolution_check.py` plus strict/version/structure/package validators: repository gate integration.
- `tools/package/pipeline.py`: exact resolved-composition embedding and output-ownership-first preflight ordering.
- `tests/test_release_compiler.py`, `tests/test_release_staging.py`, and package-pipeline architecture coverage.
- generated command/version metadata and release indices regenerated from canonical inputs.
- release/architecture documentation, repository indexes, changelog, and target-local AIDE project state.

No generated build products under `build/` are tracked by this task.
