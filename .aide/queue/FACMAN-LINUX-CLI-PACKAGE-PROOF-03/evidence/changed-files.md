# Changed Files

- `.github/workflows/ci.yml`: required zero-skip Linux package gate and
  evidence upload.
- `release/`, `contracts/schema/release/`: Linux CLI profile, tarball manifest,
  release indexes, and linkage/package-proof contracts.
- `tools/package_build.py`, `tools/package_hash_manifest.py`,
  `tools/linux_package_proof.py`: release-shaped build, integrity/linkage
  enforcement, target runtime and adversarial proof.
- `runtime/package/fl_runtime_verify.cpp`: exact Linux profile, target,
  package type, entrypoint, linkage, and component-role verification.
- `tests/`, release validators, and strict tooling: profile inventory,
  structure, workflow, schema, and package-layout regression coverage.
- `README.md`, `docs/`, and `.aide/`: bounded package claim, architecture,
  roadmap, current state, review, and WorkUnit scope evidence.

No Universal Launcher or Universal Setup source changed. Their workspace pins
remain fixed. No Factorio executable was run and no quarantined capability was
enabled.
