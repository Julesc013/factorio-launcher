# Terminal confirmation after an input edit

The retained PR425 Windows package reproduces a stale-input confirmation failure.
After the ordinary Saves form confirms snapshot name `first`, editing the name
to `second` and activating once publishes `second.zip` before navigation can
cancel it. The complete transcript has only one confirmation. The typed owner
receives `snapshot_id=second`, `confirmation=explicit` and completes normally.
Editing and cancelling without another activation preserves the full workspace.
Diagnosis: external `tui-edited-confirmation-diagnosis-packet-01.json`, SHA256
`4533415318039cc88bbcd4930486ee1a2f5e21d9596f5fe0df97ad546098ca4c`.
All eight recorded jobs close; source, registrations and the original package
remain unchanged. This is a frontend confirmation defect.

The correction only invalidates the existing pending action when an accepted
form field's value changes. Re-entering its current value retains confirmation;
an absent optional value and an empty value are equivalent. Existing validation
and the ordinary confirmation gate then require a new review before dispatch.
The action transport, typed owners, request fields, fingerprints and durable
receipts are unchanged.

Native controls cover changed names, required empty values, optional values
becoming empty or nonempty, present/absent empty no-ops, unchanged names and an
invalid-to-corrected value followed by a newly armed no-op. Public regressions
use separate fresh fixtures: one activation after the edit then Cancel must
display a second confirmation and preserve all workspace files and paths; two
activations after the edit must create only `second` with its exact typed report,
archive hash closure, selected world and preserved source/registration inputs.
Independent prebuild review admitted the correction. The existing Windows
Release cache was regenerated with integrated base c517265 and dirty source,
then rebuilt with the normal clean-first helper and two workers. Both native
TUI checks pass. The full ordinary TUI module discovers eleven methods: ten
pass, including both new regressions, and its Linux-only publication case
retains the explicit Windows skip. The immutable twenty-field backup request
and replay control passes. Engineering, format, generated metadata/contracts,
project truth, diff, strict and portable AIDE checks pass.

The external qualification retains two controller failures: the first build
used the executable output name rather than target `facman_cli` and stopped
before compilation; the second runner completed all checks but used an
incorrect native-binary directory while assembling metadata. Correct output
hashes are assembled separately without repeating the successful tests. The
source and fixture inputs remain unchanged during qualification; all recorded
command jobs stop normally and close empty. See external
`tui-edited-confirmation-author-packet-01.json` and its raw custody. Current-head
hosted CI and delivered-package acceptance remain pending. Earlier codec
endurance evidence is retained without claiming a new endurance run.

PR425's required CI and independently accepted Windows and Linux delivered
results are retained as the exact three `snapshot-producer-accepted-*-projection-01.json`
records and `snapshot-producer-accepted-projection-hashes-01.json` in this
WorkUnit's evidence directory. Custody SHA256:
`118762fe67af83932d91508ec6e826afc6e35dbc49b523d50d77ea0067d3c347`.
Only metadata is imported; the historical source pending receipt remains
unchanged. Linux delivered proof uses the separate stdlib oracle/private tmpfs;
no source schema suite, physical-ext4, human, real Play, complete F11 or release
acceptance is inferred.
