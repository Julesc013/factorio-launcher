# R3 Safety And Package Proof Checkpoint

Date: July 10, 2026 AEST.

Result: the bounded Gates 0 through 4 are complete on local task branches. R3
Safe-beta promotion is not granted. No branch was pushed, merged, or published
by this checkpoint.

## Exact Revisions

| Repository | Branch | Proof implementation revision | Scope |
| --- | --- | --- | --- |
| `factorio-launcher` | `task/facman-safety-proof-gates` | `4e6d8a191a8b17723cdd210fef2083d6814fc9b8` | evidence, confinement, truth floor, command slice, corrected package proof |
| `universal-launcher` | `task/command-registry-abi-truth` | `09e5977efd0627388da51038977ef0f5edeedfda` | registered handler path and first workflow contracts |
| `universal-setup` | `task/setup-abi-truth` | `ad129da9ac4ca86a060f5fe6c9fd31318dc44678` | ABI correctness floor and truthful unavailable verification |

The Universal Launcher branch also contains prerequisite commit `4a9f6d6` for
bounded registration and ABI guards.

## Gate Evidence

| Gate | Factorio revision | Result |
| --- | --- | --- |
| `FACMAN-EVIDENCE-LOCK-01` | `30f4374` | architecture freeze, threat model, claim ledger, and adversarial regression plan committed |
| `FACMAN-TRUST-BOUNDARY-HARDEN-01` | `a42f128` | validated identifiers, contained paths, no-clobber staging, atomic writes, and owned outputs pass regressions |
| `FACMAN-TRUTH-FLOOR-01` | `35a87e4` | read-only no-write behavior, live schema conformance, truthful refusals, and capability quarantine pass |
| `FACMAN-COMMAND-VERTICAL-SLICE-01` | `0f4a49d` | first install-to-launch-preview workflow executes through registered application handlers |
| `FACMAN-PACKAGE-PROOF-02` | `91db3ba`, `4e6d8a1` | Windows x64 static CLI package verifies, passes adversarial tests, and uses the exact non-duplicated archive name |

## Selected Package

```text
profile: windows_portable_cli_x64
target: Windows x64
linkage: static-first
entrypoint: bin/facman.exe
artifact: unsigned local portable ZIP
published: no
```

The staged proof recorded 137 hashed files and exact source revisions for all
three repositories. It ran from a package path with spaces, from Unicode and
renamed extraction paths, with package files read-only, an arbitrary current
directory, an external workspace, and an empty `PATH`. Missing contracts,
missing content, one-byte drift, extra unhashed files, link/reparse paths, and
wrong target identity are refused.

## Mechanical Validation

```text
cmake -S . -B build/native-smoke -DFLAUNCH_BUILD_NATIVE_APPS=ON -DFLAUNCH_BUILD_TESTS=ON
cmake --build build/native-smoke --config Debug
ctest --test-dir build/native-smoke -C Debug --output-on-failure
py -3 tools/strict_check.py
py -3 -m unittest discover -s tests
py -3 tools/package_build.py --profile windows_portable_cli_x64 --build-root build/native-smoke --out build/gate4-packages --dist build/gate4-dist
py -3 tools/package_hash_manifest.py --root build/gate4-packages/windows_portable_cli_x64 --verify
py -3 tools/package_runtime_smoke.py --root build/gate4-packages/windows_portable_cli_x64
```

Observed before closeout:

```text
native CTests: 3 passed, 0 failed
Python tests: 145 passed, 0 skipped on the selected Windows host
strict checks: pass
package integrity: sha256_consistent
publisher authenticity: not_proven_unsigned
```

## Claims Not Promoted

- Real Factorio write-data isolation remains unproven; `run --execute` stays
  unavailable with `isolation_not_proven`.
- General diagnostic bundle sanitization remains unproven; export stays
  unavailable with `diagnostic_export_not_safe`.
- Universal Setup package verification and all mutation remain unavailable.
- Normal production ZIP handling, archive fuzzing, crash recovery, package
  signing, publication, and cross-platform target packages remain future work.
- The C ABIs have a correctness floor but are experimental, not stable plugin
  or third-party ABI promises.
- Only the migrated workflow is authoritative through the registered command
  route; other CLI families remain candidates for incremental migration.

## Next Ordered Work

1. Review and land sibling branches in dependency order: Universal Launcher,
   Universal Setup, then FacMan; run remote CI after each repository can resolve
   the matching sibling revisions.
2. Add a pinned Windows package-proof CI lane and explicit macOS/Linux native
   package lanes before claiming those platforms.
3. Resume safe read-only discovery-provider work and migrate the next real
   consumer through the same command route.
4. Prove process-boundary isolation with a write probe, then run the documented
   operator-supplied real Factorio smoke before enabling execution.
5. Implement bounded diagnostic traversal/redaction and production archive
   handling as separate capability gates.
6. Begin Universal Setup with read-only `verify-package` and `audit-package`;
   do not begin mutation from FacMan during this R3 phase.

Dynamic plugins, full GUI expansion, networking, credentials, managed install,
server execution, auto-update, signing, and publication remain deliberately
deferred.
