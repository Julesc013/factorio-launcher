# FacMan and Universal Launcher integration proof 01

## Disposition

`FACMAN-ULK-INTEGRATION-PROOF-01` passes as a local, exact-revision,
three-repository compatibility checkpoint.

The proof binds:

| Repository | Exact revision |
| --- | --- |
| FacMan | `83980f140b365ab3206d5631db7c38db929b61fb` |
| Universal Launcher | `e78cc9f3a23f748130749ebe7241dbd1166f8b25` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |

All source trees were detached and clean. The final authoritative matrix began
with an absent build root at
`E:\Temporary\FacMan\FACMAN-ULK-INTEGRATION-PROOF-01\build-final` and completed
in 423.5 seconds.

## Accepted integration

The checkpoint accepts:

- the ULK 1.4 frontend-neutral C client and transport ABI;
- the ULK 1.5 product-neutral reference graph;
- FacMan's Factorio reference mapping and strict launch-plan validation;
- the nine-module Factorio application composition root;
- exact local dependency-pin enforcement in doctor, verification and package
  preflight;
- clean detached-worktree support in both revision and release-lock
  validation; and
- intentionally asymmetric repository branch governance.

The proof demonstrates contract and behavioral compatibility. It does not
claim byte-for-byte package identity with an older source train because source
revision and SBOM/provenance records are expected to change.

## Validation matrix

| Evidence | Result |
| --- | --- |
| Universal Launcher configure/build | Pass |
| Universal Launcher native tests | Pass, 4/4 |
| Universal Launcher strict validation | Pass |
| Universal Setup configure/build | Pass |
| Universal Setup native tests | Pass, 16/16 |
| Universal Setup strict validation | Pass |
| FacMan superbuild with TUI | Pass |
| FacMan native and installed SDK tests | Pass, 53/53 |
| FacMan AIDE Lite | Pass |
| FacMan strict validation | Pass |
| FacMan full Python discovery | Pass, 486 tests with 29 intentional skips |
| Cross-repository ownership and path boundary checks | Pass |

## Retained package proof

The retained `windows_portable_cli_x64` package records all three exact source
revisions and a clean source state.

| Property | Result |
| --- | --- |
| Runtime hash manifest | Pass, 478 files verified |
| Relocated arbitrary-CWD smoke | Pass |
| Pathless runtime | Pass |
| Python runtime excluded | Pass |
| Archive SHA-256 | `c6551405ca0d0d2f100c34b1daea92368ae51fe78e61398499c7b027c8f9ca0d` |
| Provenance SHA-256 | `d5ffaeb8dd4063c350662405dd25b6d3f02809ae25bb287bdebeb0600c0f79a9` |
| Provenance verification | Pass |
| Signing/authenticity | Unsigned; authenticity not proven |
| Publication | Not performed |

The package and proof artifacts remain under the task-owned
`E:\Temporary\FacMan\FACMAN-ULK-INTEGRATION-PROOF-01` root.

## Findings resolved during reconstruction

The first proof attempts failed closed and exposed three local-harness
assumptions:

1. package tests ignored an explicitly selected Release build root;
2. dependency and release-lock resolution rejected Git worktree `.git` files;
3. two governance assertions retained the preceding phase.

Each issue received focused regression coverage. The authoritative from-empty
matrix was run only after all three corrections passed strict validation.

## Continuing boundary

Universal Setup retains all install-mutation authority. The extracted ULK
reference contracts do not add persistence or preparation authority. The
historical instance-isolated Play candidate still requires revalidation
against the current ULK revision. No real Factorio execution, human verdict,
canonical promotion, signing or publication occurred.

Remaining launcher-neutral FacMan incubators are explicitly assigned to later
bounded WorkUnits for C++ client adapters, reference persistence, execution
foundations, client schema consolidation, and permit qualification.
