# FacMan accessibility human-test packet

State: `executable_inconclusive_template`

This packet prepares the two remaining Technical Preview accessibility rows:
`accessibility.winforms` and `accessibility.tui`. It does not close either
receipt gap. Mechanical prechecks do not constitute a human verdict.

The tracked template conforms to `facman.human_test_receipt.v1` and deliberately
defaults every journey and the overall result to `Inconclusive`. Pass is not the
default. A human tester must copy the template outside the source tree, replace
every sentinel from direct observation, and retain Fail or Inconclusive whenever
the evidence does not justify Pass.

## Exact binding and invalidation

- source revision: `601c5f49b7aa1cf4eb2b2af9733ac3e07e7ed27f`;
- source tree: `05cb5d547f64064eb52e0f9bc5d314ac9697864f`;
- provider-lock SHA-256:
  `d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00`;
- receipt schema: `contracts/schema/release/human_test_receipt.v1.schema.json`;
- tracked template:
  `docs/quality/evidence/facman_accessibility_human_test_receipt.template.v1.json`;
- package and release-resolution SHA-256: explicit zero placeholders until an
  exact candidate is rebuilt from this source.

The previous package qualification at source `6a032a45` is useful engineering
evidence but cannot fill these placeholders because product source changed.
Any source, provider lock, WinForms layout/theme/presentation adapter, TUI
router/renderer/session/schema, or package-layout change invalidates this
packet or the resulting receipt as applicable.

## Mechanical prechecks

The candidate producer supplies exact green results for these checks before
human observation begins:

```powershell
python tools/ui_accessibility_check.py
python tools/winforms_c1_runtime_smoke.py
python -m unittest tests.test_ui_accessibility tests.test_facman_winforms_c1_shell
python -m unittest tests.test_tui_product tests.test_tui_conpty tests.test_tui_pty
<stage>\bin\facman.exe product inspect --json
<stage>\bin\facman.exe package verify --json
python tools/accessibility_human_test_packet_check.py
```

These checks cover declared accessibility assets, native control construction,
UI Automation anchors, DPI mechanics, same-binary routing, terminal modes,
transcripts, resize/Unicode/ASCII behavior, and package identity. A skipped,
unavailable, or green mechanical check is not a subjective usability,
screen-reader, contrast, terminology, navigation, or scaling judgment.

## Required human judgments

Use the exact packaged WinForms and `facman` TUI binaries on the declared
Windows candidate lane. Record the Windows build, architecture, display setup,
terminal, and assistive technology in the copied receipt.

### WinForms

1. Complete every required ordinary page and action by keyboard only. Exercise
   Tab, Shift+Tab, access keys, arrows, Space, Enter, and Escape. Judge focus
   visibility/order, keyboard traps, cancellation, refusals, Activity, Last
   Run, and recovery paths.
2. With the named screen reader, judge accessible names, roles, states,
   grouping, errors, progress, refusals, Activity, Last Run, and recovery
   announcements.
3. Enable Windows High Contrast and judge legibility plus non-color-only focus,
   selection, warning, danger, refusal, and status cues across required states.
4. At 100%, 150%, and 200% display scaling, judge clipping, overlap,
   truncation, legibility, resizing, focus visibility, and access to every
   required action. Record each scale as a separate journey.
5. Judge terminology, page/action grouping, navigation, refusal language, and
   return paths against the same product semantics exposed by CLI and TUI.

### TUI

1. Operate the same `facman` binary using documented keys only. Judge focus,
   page/action navigation, cancellation, exit, and terminal restoration.
2. Use the named screen reader with linear/plain rendering. Judge reading
   order, headings, state, errors, progress, refusals, Activity, Last Run, and
   recovery output.
3. Disable color and animations where supported. Judge whether meaning, focus,
   status, and complete operation survive without color or motion.
4. Resize the terminal, exercise Unicode content, and use ASCII fallback.
   Judge whether actions remain reachable and output remains ordered/readable.
5. Judge ordinary-page terminology, actions, refusal text, Advanced handoff,
   navigation, and return paths.

## Copy, bind, and validate

Copy the tracked template to a task-owned evidence directory outside the
candidate source and fill it without editing the template. Bind
`package_sha256` to the exact candidate archive and `resolution_sha256` to the
exact `release-resolution-set.v1.json` supplied for the test. Assign a fresh
receipt/candidate identity, tester, UTC time, environment, assistive
technology, per-journey observations/verdicts, overall verdict, limitations,
and unresolved findings.

Validate the copy against both supplied artifacts:

```powershell
python tools/accessibility_human_test_packet_check.py `
  --receipt C:\facman-evidence\accessibility-human-receipt.v1.json `
  --package C:\facman-evidence\facman-candidate.zip `
  --resolution C:\facman-evidence\release-resolution-set.v1.json
```

The command validates structure, exact current source/provider binding,
artifact digests, journey completeness, verdict consistency, and closed
authority. Its success means only `structurally valid and non-authorizing`.
It does not accept the human judgment or update product/release truth.

## Verdict law and authority ceiling

- `Pass` requires every required journey to Pass and zero unresolved findings.
- `Fail` requires at least one failed journey and retains the exact defect.
- `Inconclusive` requires at least one inconclusive journey and is mandatory
  when the candidate, environment, assistive technology, observation, or
  judgment is incomplete.
- Accepted limitations must be explicit; the tracked template accepts none.
- Beta/stable/route promotion, signing, and publication remain false in every
  receipt. Tagging, support promotion, Setup mutation, and Factorio execution
  are outside this packet and remain unauthorized.

Only a later reviewed exact human receipt may close either accessibility gap.
