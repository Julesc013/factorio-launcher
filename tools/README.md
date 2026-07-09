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
