# Validation evidence

## Backend and package identity

- `facman.backend_identity.v1` is closed and required by
  `factorio.product.v1`.
- Generated command-catalog SHA-256:
  `ce90b4a7b9889a9c151aef467e016147128ca226a5fed72ad55533fab95a0aec`.
- Generated contract-set SHA-256:
  `30998a41f9b3b702e50265925dd0fb2f8469460769c94b6bab7f5fe17887f7c3`.
- The reconstructed local `windows_legacy_winforms_x64` package reports
  `sha256_consistent`, `verified=true`, exact accepted provider pins, exact
  build/contract matches, `not_proven_unsigned`, and 399 verified files.
- `python tools/winforms_backend_identity_check.py --package
  build/backend-identity-packages/windows_legacy_winforms_x64`: pass. The
  executable harness accepts the exact real handshake and refuses build,
  protocol, contract-set, provider, capability, hash, hardlink, junction,
  namespace, overwrite, and suspended-image substitutions.

## Builds and behavior

- WinForms .NET Framework 4.8 x64 Debug warnings-as-errors: pass.
- WinForms .NET Framework 4.8 x64 Release warnings-as-errors: pass.
- `python tools/winforms_transport_hardening_check.py`: pass, 38 cases.
- Canonical MSVC Debug build: pass with the process-local
  `__COMPAT_LAYER=RunAsInvoker` host-compatibility override.
- Canonical MSVC Debug CTest: 59/59 pass.
- Canonical MSVC Release build: pass with the same process-local override.
- Canonical MSVC Release CTest: 59/59 pass.

## Repository gates

- `python tools/test_obligations.py --profile promotion`: pass, 707 tests,
  zero failures/errors, zero required/unknown skips.
- Classified skips: two unsupported symlink-creation cases and one optional
  bounded full-scale performance corpus.
- Machine-readable results are retained in
  `python-test-obligations.v1.json` with `gate_passed=true`.
- The promotion profile's strict validation passed with both exact sibling
  provider pins readable.
- Dominium, C3, universal consumer, and provider contract-wave focused tests:
  pass.
- AIDE Lite, project-state, source-format, generated metadata, queue/truth,
  plan-view, diff, structured commit, and changelog-preview checks: pass.

## Authority reconciliation

- ULK and USK consumer pins are unchanged.
- No provider implementation or branch mutation occurred.
- No Factorio, synthetic fixture, successor route, Setup apply, credential,
  network, signing, publication, release, or human-verdict action occurred.
