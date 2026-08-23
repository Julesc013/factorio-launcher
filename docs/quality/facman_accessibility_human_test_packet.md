# FacMan accessibility human-test packet

State: `alpha_1_release_source_allocated_artifact_binding_pending`

This packet prepares the two remaining Technical Preview accessibility rows:
`accessibility.winforms` and `accessibility.tui`. It is evidence/configuration
for the allocated alpha.1 release source, not a human verdict and not a second
product source. It makes the human work executable after package construction
but does not close either receipt gap. Mechanical prechecks do not constitute a human verdict.

The tracked template conforms to `facman.human_test_receipt.v1`, binds product
version `0.1.0-alpha.1`, and deliberately leaves source/package/resolution
identities at zero sentinels. After source freeze and three-root qualification,
the validator derives the exact binding from the verified package and
resolution into a new no-clobber pending receipt. Every journey and the overall
result still default to `Inconclusive`. Pass is not the default.

In operational terms: derive the exact binding from the verified package and resolution;
never copy a source revision or digest into the tracked template by hand.

## Exact binding and invalidation

- allocated product version: `0.1.0-alpha.1`;
- source revision/tree: derived from the release-eligible resolution after the
  accepted release-source head is frozen;
- canonical package and release-resolution-set SHA-256: derived from the exact
  supplied files;
- resolution root, composition, and stage digests: cross-checked between the
  resolution set and embedded package stage;
- Universal Launcher:
  `5479939ca5cbc9ee0f901608a92012778b4752ae`;
- Universal Setup:
  `d2a2aae7e61c47035c92334b0522143b4fea3880`;
- provider-lock SHA-256:
  `d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00`;
- receipt schema: `contracts/schema/release/human_test_receipt.v1.schema.json`;
- tracked template:
  `docs/quality/evidence/facman_accessibility_human_test_receipt.template.v1.json`;

The alpha.0 development precursor remains qualified by
`docs/release/checkpoints/facman-candidate-v2-final-source-qualification-01.md`,
but its bytes are not accepted as alpha.1. The validator checks the alpha.1 ZIP
bytes and canonical filename, embedded stage identity, resolution-set bytes,
resolution root, resolved-composition digest, source tree, and provider commits
before human execution. Any source, provider lock, WinForms
layout/theme/presentation adapter, TUI router/renderer/session/schema, package
layout, or bound resolution change invalidates this packet or the resulting
receipt as applicable.

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

## Verify, copy, observe, and validate

First derive an exact pending receipt from the qualified alpha.1 artifacts.
The resolution file must remain beside its exact
`resolved-composition.v1.json` sibling. The output is no-clobber:

```powershell
python tools/accessibility_human_test_packet_check.py `
  --bind-output C:\facman-evidence\accessibility-alpha-1-pending.v1.json `
  --package C:\facman-evidence\facman-0.1.0-alpha.1-windows-winforms-x86_64-technical-preview.zip `
  --resolution C:\facman-evidence\resolution\release-resolution-set.v1.json
```

Then verify that exact pending receipt against the same files:

```powershell
python tools/accessibility_human_test_packet_check.py `
  --pending `
  --receipt C:\facman-evidence\accessibility-alpha-1-pending.v1.json `
  --package C:\facman-evidence\facman-0.1.0-alpha.1-windows-winforms-x86_64-technical-preview.zip `
  --resolution C:\facman-evidence\resolution\release-resolution-set.v1.json
```

Success means only that the exact artifacts are bound and the packet is ready
for human execution. Every journey and the overall verdict remain
`Inconclusive`; every authority remains false.

Copy the tracked template to a task-owned evidence directory outside the
candidate source and fill it without editing the template. Keep the exact
candidate identity and artifact hashes. Assign a fresh human receipt identity,
tester, UTC time, environment, assistive technology, direct per-journey
observations/verdicts, overall verdict, limitations, and unresolved findings.

Validate the copy against both supplied artifacts:

```powershell
python tools/accessibility_human_test_packet_check.py `
  --receipt C:\facman-evidence\accessibility-human-receipt.v1.json `
  --package C:\facman-evidence\facman-candidate.zip `
  --resolution C:\facman-evidence\release-resolution-set.v1.json
```

The command validates structure, exact frozen source/provider binding, package
and resolution identity, journey completeness, verdict consistency, and closed
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
