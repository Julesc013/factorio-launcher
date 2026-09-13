# Validation

`integrated-closeout.v1.json` binds the final result to protected `dev` merge
`4ae50d6e1b72a1ffa967c54642168e2028677a32`, tree
`950676fec250c9c791a363eca4e16cbcdcdd1a75`.

- PR 266 passed all eleven required `dev` checks. Windows job 103706334167
  passed its 37 substantive steps, including the WinForms gallery, package
  proofs, deterministic self-setup and package-composition proof.
- The current Windows gallery passed 6,729 assertions across 28 render cells
  and one constrained cell. Receipt SHA-256:
  `ef90bd76a9598196c2876e29d36d842dfd7a53ef121222b1f6248319b7a66a1d`.
- The hosted GTK gallery passed 19,088 assertions across 56 render cells and
  5,408 mapped font-label observations with no missing-font cell. Receipt
  SHA-256: `d12a15768251deac0f7880038994f44fc8c136eb5ec015a695310a04b3323676`.
- The exact hosted self-setup payload supplied the current managed assembly to
  the source-bound gallery probe. It remained distinct from the native CLI and
  repeated all 6,729 assertions. Result SHA-256:
  `af10066b48fa92b9653d3e4f14538f1cbd4b93ea78e33de2915013ed796ab834`.
- The first packaged run retained its GDI+ path-length failure after 28 normal
  cells. The identical inputs passed from the shorter owned path; no failed
  observation was rewritten.

The final generated-plan check, project-state validation, 40 plan-view unit
tests, full strict repository check (417 schemas), portable AIDE Lite test and
`git diff --check` all pass. A fresh non-authoring GPT-5.6 Sol review returned
PASS; its exact scope and retained authority boundaries are recorded in
`integrated-closeout-review.v1.json`.
