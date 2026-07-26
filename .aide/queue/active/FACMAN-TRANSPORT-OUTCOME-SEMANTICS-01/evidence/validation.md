# Validation

Local promotion validation is complete for the transport-outcome implementation
based on FacMan `dev` parent
`3c4fb175272f3d7b160ab87f32b632985ea65d39`, Universal Launcher provider
`7fc25340623131ba86c08dca4fb8a43b18a4520d`, Universal Launcher `main`
`7f4312faf2f1ac2856a51393fef0ec49fc276a78`, and Universal Setup
`3f8489275077347c2918f3bb03614ec6431362ff`.

- Published ULK native contract matrix: pass on Windows, Linux, and macOS.
- FacMan MSVC Release native matrix: 53/53 passed.
- Python promotion obligation matrix: 515/515 passed.
- Required blocked skips: 0.
- Unknown skips: 0.
- Optional skips: 7.
- Unsupported platform-feature skips: 2.
- Machine transport v1 compatibility and v2 outcome round trips: pass.
- Direct cancellation/completion race and process post-dispatch uncertainty:
  pass.
- Generated WinForms compile smoke: pass.
- Generated frontend transport truth: 3/3 passed.
- Schema validator: 298 schemas passed.
- `python tools/project_state.py`: pass.
- `python tools/strict_check.py`: pass.
- `python .aide/scripts/aide_lite.py test`: pass.
- `python tools/aide_queue_state_check.py`: pass.
- `python tools/aide_compaction_check.py`: pass.
- `git diff --check`: pass with line-ending conversion notices only.

The machine-readable Python result and complete runner logs are retained beside
this file. Hosted FacMan validation is pending for the exact committed head.

No Factorio process, permit issuance, WPR capture, route promotion, policy
change, Setup mutation, network authority, credential authority, or product
execution occurred.
