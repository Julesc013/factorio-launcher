# Changed Files

- `external/miniz/`: exact source-only Miniz 3.1.2 release, upstream license,
  README, changelog, and FacMan provenance record.
- `CMakeLists.txt` and `tests/native/miniz_dependency_smoke.c`: private static
  build integration and executable capability smoke.
- `docs/architecture/decisions/archive-dependency-admission.md`: dependency,
  license, capability, alternative, and forced-ZIP64 validation decision.
- `THIRD_PARTY_NOTICES.md`: MIT redistribution notice.
- `release/index/dependency_lock.v1.toml` and `sbom.components.v1.json`: exact
  source, archive digest, license, linkage, and transitive-dependency records.
- `tools/validators/release/check_dependency_lock.py` and
  `tests/test_archive_dependency_admission.py`: machine-enforced admission.
- AIDE queue/profile files: WorkUnit scope and evidence only.

No archive consumer, Factorio runtime operation, frontend route, or capability
flag changed.
