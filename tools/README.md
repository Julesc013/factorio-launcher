# Tools

Owns repository automation.

Python is appropriate here for validators, schema checks, fixture generation,
package checks, project graph reports, and one-off migration helpers.

Tools must not become FacMan product runtime dependencies.

Workspace proof tools:

- `cross_repo_check.py` validates product-only and sibling-repo boundaries.
- `workspace_config.py doctor` resolves machine-local Universal repositories
  and rejects a `HEAD` that differs from the workspace lock. It never aligns
  or changes dependency branches.
- `verify_dependency_revisions.py` performs the same read-only check directly;
  `--align` is reserved for explicit hosted checkout preparation.
- `repro_workspace_smoke_v2.py` validates both supported FacMan directory names
  in a reproducible three-repo checkout and
  can optionally run the full build/test matrix with `--build`.
- `windows_stable_build_root.py` gives sequential Windows clean builds a
  collision-checked, short-lived logical root so MSVC anonymous-namespace
  identities remain byte reproducible across different physical checkout
  paths. It refuses occupied drives and always removes its mapping.
- `alpha_vertical_slice_check.py` validates golden JSON examples for the current
  FacMan alpha command surface.
- `refusal_golden_check.py` validates that command refusal goldens use the common
  FacMan refusal contract.
- `release_contract_check.py` runs the release/distribution validators under
  `tools/validators/release/`.
- `facman_release.py` exposes deterministic release-model validation,
  out-of-tree source-observation projection, per-target resolution,
  explanations, diffs, safe release-build staging, stage verification, bounded
  package inspection, and adapter round-trip verification.
- `release_resolution_check.py` keeps the three first-family CLI targets,
  compatibility projections, provider maturity, authority, claims, ten
  canonical child records, aggregate root, and runtime projection
  deterministic and fail-closed under `strict_check.py`.
- `release_resolution_integration_check.py` enforces tracked/observed source
  separation, bounded package metadata, exhaustive producer custody, exact
  forward-only commit exceptions, and the canonical integration plan.
- `universal_delivery_programme_check.py` keeps source/SDK conformance and
  provider adoption planned, preserves source consumption and withheld release
  authority, and verifies that every later provider/product programme wave is
  registered as a trigger rather than activated by documentation.

Gate 4C evidence tools:

- `gate4c_verdict_preflight.py` creates a hash-closed, non-executing preflight
  record for the exact frozen Windows x64 / Factorio 2.0.77 / standalone /
  menu / hermetic candidate. Missing source, observer, host, repository, or
  instance evidence is a blocker. Source evidence must be either a recognized,
  exact-version Wube installer or an operator-supplied standalone ZIP package
  containing the exact installed executable. Portable packages are bounded and
  structurally inspected; the task-owned inspection copy must match the package
  member and installed executable byte-for-byte, and that member must carry a
  valid Wube signature and exact `2.0.77` version metadata. Package contents do
  not prove entitlement. Quiet-host attestations expire after 10 minutes and
  bind the current machine, boot, observer proof, and host-state digest. The
  tool cannot issue a permit or start a process.
- `gate4c_observer_self_test.py` is an elevated Windows-only ETW self-test for
  the independent FileIO, Registry, and process observation prerequisites. It
  binds the current machine/boot, exact FacMan tooling commit and script hashes,
  the materialized byte hash and reviewed LF-normalized canonical hash of
  `gate4c_process_tree_observer.wprp`,
  WPR/XPerf/WPAExporter identities, and its trace/dump/stats hashes. The custom
  profile enables only `ProcessThread`, `FileIO`, `FileIOInit`, and `Registry`;
  it uses one file-mode kernel collector with 1 MiB buffers and 256 buffers,
  with no stacks or user-mode event providers. The XPerf dumper output is
  parsed as positional CSV: FileIO, Registry, and child-process events must
  each match the unique marker, expected event class, and event-specific PID
  field on the same row; process start must also match the exact parent PID. All
  three executables must come from one coherent Windows Performance Toolkit
  root; a PATH-selected system WPR mixed with toolkit decoders is refused. WPR
  status is rechecked after stop before cleanup responsibility is released.
  The live `wpr -status collectors -details` loss counters and any WPR
  stop/XPerf loss report are combined, and any nonzero or unresolved loss
  remains Inconclusive. Self-tests expire after 15 minutes.
  The tool exercises only task-owned probe state and cannot start Factorio or
  record a human verdict.
- `gate4c_verdict_session.py` exposes the frozen observer backend used only by
  the one-shot high-integrity Gate 4C broker. Its closed operations are start,
  status, finish, and fail-closed abort; it cannot launch Factorio.
- `gate4c_privilege_separation_check.py` validates the medium-integrity
  coordinator/game boundary, high-integrity observer-only boundary, closed
  named-pipe protocol, pre-resume token validation, evidence schemas, and
  unchanged no-authority truth.
