# FacMan candidate assurance and release-readiness 01

Date: 16 August 2026

State: `review_ready_stacked_noncanonical`

## Outcome

Independent review of the complete candidate stack found and closed two
release-blocking operator-boundary defects. Isolated real-process execution is
now independently default-off instead of inheriting the ordinary test graph,
and the separate engineering harness consumes an explicit digest-bound route
record instead of embedding its build-machine source path.

This successor remains stacked on the noncanonical Factorio 2.1.14 engineering
route. It changes no canonical provider pin, release route, protected ref,
signing state, publication state, or support authority.

## Reusable assurance

`tools/candidate_security_assurance.py` performs fail-closed source, stage, and
ZIP inspection. It checks safe and unique ZIP paths, case collisions, the
exact binary allowlist, operator/test payload exclusion, local-path and token
markers, licence and SBOM closure, component digests, canary authority, and
stage-to-ZIP byte identity.

`tools/windows_private_route_bundle.py` and
`tools/windows_private_route_guest.ps1` prepare a local Windows Sandbox replay
from exact candidate, harness, route-record, private-archive, and Factorio
executable digests. The guest has networking and host-device redirection
disabled, receives three narrow read-only input mappings and one writable
evidence mapping, safely extracts ZIPs, redirects user state into one fixed
task root, runs package/Doctor/TUI checks, supervises launch and relaunch,
requires authoritative completed Last Run records, rehashes the inputs, and
removes only its task-owned guest root.

The private archive is never added to the candidate or uploaded. Host staging
uses a hard link where possible and requires an explicit local-copy fallback
otherwise.

## Direct proof

The independently built relocated harness:

- contains no FacMan source, build, provider, user-profile, or old branch path;
- rejects a digest-mismatched route record before process creation;
- supervised the exact isolated Factorio 2.1.14 executable to a clean exit;
- recorded authoritative running and terminal Last Run state;
- preserved the complete 20,832-file, 5,350,965,797-byte source inventory; and
- left no Factorio process running.

The current noncanonical candidate passed the new package security scan. Its
five shipped binaries are the exact expected allowlist; the operator harness,
fake executor, debug artifacts, private archive markers, local build paths, and
credential patterns are absent. Unsigned Authenticode state remains expected
and explicit.

Exact receipts, binary identities, private-input digests, and hosted checks
belong to the task evidence packet and pull request rather than this source
checkpoint.

## Remaining gates

1. Integrate ULK PR #16 and FacMan PR #154 through independent protected paths.
2. Adopt the resulting exact canonical ULK `main` identity.
3. Forward-integrate and requalify the complete FacMan stack on canonical
   `dev`; do not reuse current package or route receipts.
4. Complete the frozen subjective accessibility and usability review.
5. Obtain separate signing, publication, and support authority.

Work-Item: `FACMAN-CANDIDATE-ASSURANCE-RELEASE-READINESS-01`
