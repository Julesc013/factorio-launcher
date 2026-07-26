# Gate 4B validation evidence

## Accepted implementation

PR #52 merged reviewed head
`da3e2274a3dc8a5757078b20276a1a6a93084860` into `dev` at
`e9c1e69fee1ae815f62638db8b7263cb01b70389`.

The accepted candidate verifies the immutable Gate 4A policy digest
`6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`
and remains limited to Windows x64, Factorio 2.0.77, authenticated standalone
non-Steam source evidence, `menu`, `hermetic`, an explicit empty mod lock, no
account, no credential, and no network.

## Exact reviewed-head hosted proof

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `29909515085` | `29909518558` | Pass |
| Code security | `29909515064` | `29909518660` | Pass |
| Schema check | not triggered | `29909518641` | Pass |
| Security policy | `29909514463` | `29909518606` | Pass |

The final head passed duplicate Linux GCC, macOS AppleClang, Windows MSVC,
coverage, sanitizer, real bounded fuzz, package/reproducibility, WinForms,
AppKit, TUI, strict, Python, schema, security-policy, and CodeQL jobs.

Earlier heads exposed and repaired three honest cross-platform/test issues:

1. a deeply nested Windows clean-reproduction journal path;
2. Windows-only product and fixture helpers compiled unused on Linux/macOS;
3. a GCC range-loop temporary-binding warning in the candidate fixture.

No failure was waived or hidden. Each correction is a separate structured
commit and the full matrix was restarted at the final head.

## Exact merged-`dev` proof

| Proof | Run | Result |
| --- | --- | --- |
| CI | `29910544402` | Pass |
| Code security | `29910544923` | Pass |
| Schema check | `29910545091` | Pass |
| Security policy | `29910544435` | Pass |

## Clean pinned three-repository reproduction

One detached, no-hardlink reconstruction used:

| Repository | Revision |
| --- | --- |
| FacMan | `da3e2274a3dc8a5757078b20276a1a6a93084860` |
| Universal Launcher | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |

Universal Launcher and Universal Setup each configured, built, passed native
CTest, and passed strict validation. FacMan configured, built, passed its
TUI-enabled native matrix (48/48), AIDE Lite, strict validation, and its full
Python suite. The serial matrix completed in 548.3 seconds and every detached
source checkout remained clean at its exact pin.

The final contract state is 125 command contracts, 123 registered routes, 279
schemas, and 242 refusal codes. Local implementation proof also passed the
47-test non-TUI configuration and 375 Python tests with 313 target-specific
skips.

## Disposition

Gate 4B closes only as:

```text
eligible_for_human_verdict
```

It does not record `Pass`, `Fail`, or `Inconclusive`; issue a reusable product
permit; expose public Play; run Factorio; or promote any authority.

## Closeout and public-integration proof

PR #53 merged the evidence-only closeout head
`e60ff931317aaa6a68b7cbfd820afb4b4fce3676` into `dev` at
`7fe12635f7309e4fd709810dd192d43ff920592f`.

The closeout head passed push CI `29911647564`, push code-security
`29911647498`, push security-policy `29911647205`, pull-request CI
`29911672399`, pull-request code-security `29911672382`, and pull-request
security-policy `29911672471`. The truth-only diff did not trigger the
path-filtered schema workflow; local strict validation passed all 279 schemas.

The exact closeout merge revision passed CI `29912502213`, code-security
`29912502124`, and security-policy `29912502140`. The schema workflow again
did not trigger for the truth-only path set, and no schema or contract changed.

This closes Gate 4B as `eligible_for_human_verdict` and activates Gate 4C. It
does not record a human verdict, make FacMan playable, or promote execution or
permit-issuance authority.
