# Tools

Owns repository automation.

Python is appropriate here for validators, schema checks, fixture generation,
package checks, project graph reports, and one-off migration helpers.

Tools must not become FacMan product runtime dependencies.

Workspace proof tools:

- `cross_repo_check.py` validates product-only and sibling-repo boundaries.
- `workspace_config.py` prints machine-local Universal repo paths and CMake
  arguments.
- `repro_workspace_smoke.py` validates a reproducible three-repo checkout and
  can optionally run the full build/test matrix with `--build`.
- `alpha_vertical_slice_check.py` validates golden JSON examples for the current
  FacMan alpha command surface.
- `refusal_golden_check.py` validates that command refusal goldens use the common
  FacMan refusal contract.
- `release_contract_check.py` runs the release/distribution validators under
  `tools/validators/release/`.

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
  WPR/XPerf/WPAExporter identities, and its trace/dump/stats hashes. File,
  Registry, and child-process events must each match the expected PID and event
  class. All three executables must come from one coherent Windows Performance
  Toolkit root; a PATH-selected system WPR mixed with toolkit decoders is
  refused. WPR status is rechecked after stop before cleanup responsibility is
  released. Self-tests expire after 15 minutes. The tool exercises only
  task-owned probe state and cannot start Factorio or record a human verdict.
