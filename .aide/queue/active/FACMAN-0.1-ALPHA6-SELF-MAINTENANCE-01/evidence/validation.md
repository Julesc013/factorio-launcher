# Validation

Source base: `c65c66ade1d4ca2c0c03b6b9aa78bfea2b977ae6`

Passed on 2026-09-16 in the marker-owned external task root against pinned
Universal Setup `279ad4876dc325f8e1fcdc918c91b098a11bc616` and Universal
Launcher `5479939ca5cb`:

- `py -3 tools/dev.py build developer --target facman_self_setup_recovery_smoke --configuration Debug`
- direct execution of the Debug recovery smoke: 62 checks passed
- `py -3 tools/dev.py build product --target facman_setup --configuration Debug`
- `py -3 -m unittest tests.test_self_setup_recovery_contract tests.test_package_manifests tests.test_product_candidate_workflow`: 36 tests passed; all 29 package manifests, 19 bundle layouts, 14 release profiles, and 14 package skeletons passed their checks
- `py -3 -m py_compile tests/integration/facman_self_setup_lifecycle.py`
- synthetic `facman_self_setup_lifecycle.py` against the built Debug setup executable
- AIDE task inspect/noop checks classify the WorkUnit as active/partial and
  direct continued work from its status and evidence
- `py -3 tools/project_state.py --write` and
  `py -3 tools/codegen/generate_metadata.py --write`, together with the
  canonical mutable-queue index projector and `tools/generate_plan_views.py`,
  refreshed their projections after activation and predecessor integration; all
  10 pre-existing `.aide/reports` files were byte/timestamp verified against an
  external snapshot, the two task-classification report absences were
  preserved, and the report tree retained no additional file
- the final `py -3 tools/strict_check.py` passed, including plan views, queue
  state, 426 schemas, package/profile/layout/skeleton checks, setup workflow,
  refusal contracts, code generation, security, and source formatting

The predecessor setup/native recovery WorkUnit has an exact integrated partial
checkpoint: PR #292 source `6ef1a9d3c95523b4e2b36aa5277ef498f555d523`,
source/merge tree `6fdbda15fd22db01c4de0794efed790a22b837ff`, CI run
`34976666277`, Windows package job `104406007552`, protected promotion rerun
`34976666335`, and dev integration
`c65c66ade1d4ca2c0c03b6b9aa78bfea2b977ae6`. The predecessor remains active
because that receipt does not qualify update/downgrade recovery. It also does
not qualify locked-file restart handoff or this WorkUnit's closure.

The real current-user lifecycle gained produced-package cases for uninstall
with the repair ZIP withheld, fresh registered repair with the ZIP withheld,
and plan-reviewed repair resumed from retained input. Those cases remain for
the gated Windows candidate job; they were not run against this workstation's
real Start Menu and HKCU registration.

Independent lifecycle review passed the runtime slice. Its first evidence
review rejected an incorrect terminal claim for the predecessor WorkUnit,
whose acceptance also requires update recovery. The predecessor task, status,
canonical plan and generated views now remain active/PENDING; its exact PR #292
receipt is explicitly PARTIAL with `workunit_closed=false`. The independent
re-review returned PASS after that correction.
