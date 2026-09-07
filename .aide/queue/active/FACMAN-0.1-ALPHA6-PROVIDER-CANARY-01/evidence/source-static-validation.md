# Source-static slice validation

The local source-static slice passed. The whole provider canary remains active and PENDING;
installed/shared/relocated consumption, consumer interruption/replay and independent final
review remain outstanding. Stable pins, provider publication and adoption are unchanged.

The consumer base is `b98fc920a0765f21ae5bd38907a902c8f2572f04`. Its uncommitted source delta is
bound by the external source manifest; the actual binary correctly reports dirty SDK-candidate
source and release-incoherent provider identity. It consumes clean local USK
`8d02dfcbf7f7e16308b37815eb7c91d0beb668be` and unchanged stable ULK
`5479939ca5cbc9ee0f901608a92012778b4752ae`.

The marker-owned task root is `facman-0.1-al-b48460c353`. Evidence paths below are relative to
that external task root and will be bound in the independent-review packet.

- `c1/evidence/observation.json`: source-static configure/build PASS; four native tests PASS;
  actual FacManSetup stored and Deflate lifecycle PASS; all five stable inputs and source
  bytes unchanged during the run. SHA256:
  `1d76daad2f91c6b75f29bb2bf7d033f9097341baa0f1cf22be5378995b2a4d0c`.
- `evidence/canary-causal-oracle-replay.json`: tightened Python assertions require the actual
  decoded CRC error and truncated-payload error. Both lifecycle variants pass using the same
  setup executable, with raw responses and effect inventories in `t/c2-stored` and
  `t/c2-deflate`. This test-only delta followed the preserved C1 build.
- `evidence/canary-cli-readonly-probes.json`: actual product and command-graph inspections
  PASS; the new explicit workspace remains empty. SHA256:
  `65bbb5f0f52105b3617b956719c3008111fe058df92abfe0d1347eb22641f0e3`.
- `evidence/canary-prebuild-focused.log`: 70 successful focused checks and one import error.
  `evidence/canary-prebuild-architecture-pinned.log` reruns the affected suite with the pinned
  interpreter and correct test import path: 25 PASS. Together, 95 distinct focused tests pass.
- `evidence/canary-prebuild-strict-corrected.log`: full strict PASS after schema title,
  generated queue ordering and documentation-width corrections. Original failures remain.
- `evidence/local-source-before-admission.json`: preserved original refusal of the honest
  local task ref with no origin counterpart. The new path is explicit and candidate-only.

The six actual consumer/test executables and two compiler-identification executables are
individually hashed in the C1 observation. Synthetic Factorio files are never executed. CRC
refusal must not publish a target or alter the input/sentinel; retained state remains allowed.
Strong successful commit authority, generation/stale-owner recovery and retained cleanup
remain open provider obligations. Observational legacy commit checks are not atomic authority.

Independent review reproduced a concealed-source P2 with assume-unchanged and skip-worktree
flags. The immutable v1 source/evidence packet and raw reproduction are preserved externally.
The repaired observer refuses flagged/sparse states, unsupported entries and custom filters;
it compares bounded physical bytes to the reviewed commit without executing clean filters.
The 15 final focused custody tests pass, including actual Git/CMake refusal and filter
nonexecution. Full strict passes. With the prior 85 other focused tests, 100 distinct tests pass.

The fresh `c3/evidence/observation.json` records configure/build PASS, four native tests PASS,
and both stored/Deflate full setup lifecycles PASS with causal CRC/truncation refusals. All 286
USK tracked file observations match before configure, before build, after build and after tests;
consumer source and five stable inputs stay unchanged. This is sequential observation, not an
atomic build lease. `evidence/canary-c3-cli-readonly-probes.json` also records both read-only CLI
probes PASS with an unchanged empty explicit workspace. C1 binaries and fixtures stay retained.
The repaired source now awaits final independent review; the whole task remains PENDING.
