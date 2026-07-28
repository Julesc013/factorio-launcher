# Validation

Local promotion validation is complete for the transport-outcome implementation
based on FacMan `dev` parent
`3c4fb175272f3d7b160ab87f32b632985ea65d39`, Universal Launcher provider
`7fc25340623131ba86c08dca4fb8a43b18a4520d`, Universal Launcher `main`
`7f4312faf2f1ac2856a51393fef0ec49fc276a78`, and Universal Setup
`3f8489275077347c2918f3bb03614ec6431362ff`.

- Published ULK native contract matrix: pass on Windows, Linux, and macOS.
- FacMan TUI-enabled MSVC Release native matrix: 54/54 passed.
- Python promotion obligation matrix: 517/517 passed.
- Required blocked skips: 0.
- Unknown skips: 0.
- Optional skips: 2.
- Unsupported platform-feature skips: 2.
- Machine transport v1 compatibility and v2 outcome round trips: pass.
- Direct cancellation/completion race and process post-dispatch uncertainty:
  pass.
- Generated WinForms compile smoke: pass.
- Generated frontend transport truth: 3/3 passed.
- Functional TUI product scenarios: 3/3 passed.
- Schema validator: 298 schemas passed.
- `python tools/project_state.py`: pass.
- `python tools/strict_check.py`: pass.
- `python .aide/scripts/aide_lite.py test`: pass.
- `python tools/aide_queue_state_check.py`: pass.
- `python tools/aide_compaction_check.py`: pass.
- `git diff --check`: pass with line-ending conversion notices only.

The initial hosted PR head exposed two TUI structured-output errors on macOS:
locally synthesized cancellation and daemon refusals carried valid operation
results but had no provider payload or envelope for the structured renderer to
print. The repair emits a builder-generated `facman.tui_response.v2` only for
that empty-body boundary, preserves legacy top-level outcome and refusal fields,
and includes the exact ULK operation projection. It also makes the TUI product
test honor the configured CLI path instead of selecting a stale local binary.

The repaired exact head
`b962b1340f55c4eb2dddbe126887b369df7d5422` passed both hosted macOS native/TUI
lanes, both AppKit compile lanes, both Linux native lanes, both Windows native
package lanes, both coverage lanes, all C/C++, C#, Python and CodeQL security
checks, schema checks and security-policy checks. Pull request 77 merged into
`dev` at `c47bdc3362f7dfbaccd6cee069318270c081272e`.

Exact pull-request workflow runs:

- CI: `30209419784`.
- Code security: `30209419767`.
- Schema check: `30209419787`.
- Security policy: `30209419762`.

The machine-readable Python result and complete runner logs are retained beside
this file. Hosted FacMan validation is complete for the exact repaired head.

No Factorio process, permit issuance, WPR capture, route promotion, policy
change, Setup mutation, network authority, credential authority, or product
execution occurred.
