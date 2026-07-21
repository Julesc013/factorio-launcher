# Gate 3 OperationPermit infrastructure closeout

## Disposition

Gate 3 is accepted on reviewed `dev` as an infrastructure-only authority
boundary. PR #42 merged the reviewed implementation head
`5f9f122d6d3e95a006c44e46ba54c0927e9d288c` at `dev` revision
`91c2aa4fe0a30be97bf16165b41a95a8fab4cd11`.

The accepted result can canonically encode and authenticate one exact,
short-lived operation permit, validate it without consuming it, and let one
independent dormant provider atomically consume it once. It does not expose a
public issuer, execute Factorio, or grant product authority.

## Accepted contract and implementation

The reviewed implementation provides:

- seven versioned schemas for claims, envelopes, resources, provider and policy
  bindings, validation, and consumption results;
- one canonical claims encoding with deterministic, typed, closed resource,
  effect, and capability sets;
- an envelope authenticated with process-session HMAC-SHA-256 through a
  versioned authenticator boundary;
- explicit caller-supplied secure entropy, session-bound lifetime, strict UTC
  timestamps, injected wall and monotonic clocks, and bounded TTL policy;
- non-consuming admission validation separated from atomic one-time provider
  consumption;
- a bounded process-lifetime issuance, revocation, and replay ledger;
- 25 structured permit refusal codes rather than one generic invalid result;
- nine path-free Factorio resource bindings projected from the accepted Gate 2
  instance evidence;
- independent dormant Factorio launch-provider revalidation and consumption;
- strict refusal of wildcard, missing, extra, duplicate, reordered-to-different,
  stale, wrong-provider, wrong-operation, wrong-intent, and wrong-isolation
  authority;
- a standalone parser/adversarial corpus and a bounded libFuzzer target.

The dormant provider accepts only the internal foundation proof operation with
`menu`, `hermetic`, `workspace_read`, and `foundation.permit.verify`. It rejects
`instance.play`, reports execution unavailable, and cannot construct or submit
a process request.

## Exact reviewed-head proof

The exact PR #42 head passed:

| Proof | Run | Result |
| --- | --- | --- |
| CI | `29825371714` | Pass |
| Code security | `29825371722` | Pass |
| Schema check | `29825371753` | Pass |
| Security policy | `29825371793` | Pass |

CI included Linux Debug and Release, changed-source clang-tidy coverage,
sanitized full CTest and corpus execution, a 1,000-run libFuzzer invocation,
coverage, Windows Debug and Release, WinForms, macOS native and AppKit proof,
all three portable-package and reproducibility lanes, and the full Python and
strict suites.

The first Linux attempt passed all 47 native tests but failed the
changed-source clang-tidy guard because the conditional libFuzzer entry point
had no normal-build compile command. The reviewed correction compiled that
entry point in the standalone corpus target and instrumented the permit static
library in the fuzz configuration. No allowlist exemption was introduced.

## Exact merged-`dev` proof

The exact merged revision passed:

| Proof | Run | Result |
| --- | --- | --- |
| CI | `29826221338` | Pass |
| Code security | `29826221318` | Pass |
| Schema check | `29826221373` | Pass |
| Security policy | `29826221366` | Pass |

The local canonical matrix also passed:

- Visual Studio 2022 x64 Debug configure and warnings-as-errors build;
- full native CTest, 47 of 47;
- full Python suite, 364 passed and 2 skipped;
- strict contract state: 268 schemas, 242 refusal codes, 125 command
  contracts, 123 registered routes, and 530 SPDX-covered source files;
- standalone permit corpus, source-format, CMake architecture, code-security,
  capability-policy, project-state, and AIDE Lite checks.

## Clean pinned reconstruction

One fresh, detached and clean reproduction root used these exact revisions:

| Repository | Revision |
| --- | --- |
| FacMan | `91c2aa4fe0a30be97bf16165b41a95a8fab4cd11` |
| Universal Launcher | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |

All three repositories configured, built, tested, and passed their strict
checks. FacMan additionally passed AIDE Lite and its complete Python suite. The
single-writer run completed in 442 seconds and all three source worktrees
remained clean and exact at their pins.

An earlier attempt is retained as inconclusive environmental evidence: the
calling shell timed out after two minutes while its MSBuild child still held
the interrupted output tree, and an immediate retry against that same tree met
a PDB writer collision. No source or product test failed. The final run used a
new output directory after confirming the old process had exited.

## Authority boundary

This checkpoint does not promote:

- public or product permit issuance;
- real `instance.play` or any Factorio process execution;
- instance preparation or installation apply;
- Setup, credential, network, host-mutation, signing, or publication authority;
- a human Play verdict, Safe beta, or canonical `main`.

Permits are not portable instance state, are invalid after issuer-session
restart, and are not persisted or logged in full. Readiness and plans remain
non-authoritative. The platform CSPRNG adapter, frozen executable and launch
plan identities, issuance policy, process supervision, post-run observation,
and human evidence remain later work.

## Next programme

`FACMAN-HERMETIC-STANDALONE-PLAY-POLICY-01` is active. It is policy-only and
must freeze the exact standalone candidate, protected and writable roots,
evidence, interruption matrix, observation method, and `Pass`/`Fail`/
`Inconclusive` human criteria without issuing a permit or launching Factorio.

Only a later reviewed `FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01` may
implement the frozen route. A separate
`FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01` must perform the operator-reviewed
run. A Pass can authorize only the exact candidate class that was actually
proved.
