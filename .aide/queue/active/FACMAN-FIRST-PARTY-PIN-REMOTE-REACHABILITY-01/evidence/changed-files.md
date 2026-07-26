# Changed files

## Accepted provider truth

- `release/index/workspace_lock.v1.toml`
- `release/index/dependency_lock.v1.toml`
- `release/index/sbom.components.v1.json`
- `THIRD_PARTY_NOTICES.md`
- `.aide/memory/project-state.md`
- `.aide/memory/project-state.v2.json`

The accepted Universal Launcher source pin is
`fbb0cc87a14e8e4b26d74088a791dc83ebd4337d`. Universal Setup remains pinned at
`3f8489275077347c2918f3bb03614ec6431362ff`.

## Pin verification and release validation

- `contracts/schema/release/workspace_lock.v1.schema.json`
- `tools/verify_dependency_revisions.py`
- `tools/validators/release/check_workspace_lock.py`
- `tools/validators/release/check_dependency_lock.py`
- `tools/compliance_check.py`
- `tests/test_dependency_revision_enforcement.py`
- `tests/test_setup_package_routing.py`
- `tests/test_aide_compaction.py`

The normal validator remains offline and verifies exact clean local checkouts.
The explicit `--remote` mode proves each declared provider commit from a new
object database fetched from its declared canonical ref.

## Generated build identity

- `CMakeLists.txt`
- `cmake/FacManBuildIdentity.hpp.in`
- `runtime/factorio/CMakeLists.txt`
- `runtime/factorio/application/handlers/intelligence.cpp`

The runtime provider identity is generated from the exact configured checkouts
and checked against the workspace lock. Configuration refuses a mismatch.

## Native validation repairs

- `runtime/base/fl_path_safety.cpp`
- `tests/native/fl_path_safety_smoke.cpp`
- `tests/native/facman_process_probe.cpp`
- `tests/native/m1_three_repository_system_proof.cpp`

The managed-path check now derives a lexical descendant from the canonical
workspace root without canonicalizing an absent leaf. The Windows crash probe
uses a deterministic exception-shaped termination status so unattended tests
cannot be captured indefinitely by Windows Error Reporting. The M1 failure
message now retains the underlying repository error.

## WorkUnit records

- `.aide/queue/index.yaml`
- `.aide/queue/active/FACMAN-FIRST-PARTY-PIN-REMOTE-REACHABILITY-01/`
