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

## Hosted coverage timeout remediation

PR #296 run `34988087343`, job `104445285350`, checked out exact source
`9b42bf7f418c2c1fb9230fb41bc65ba3484f48d8`. Its coverage lane passed 46 of
47 CTests and passed coverage evidence generation and policy enforcement, but
`facman_self_setup_recovery_smoke` reached its 30-second CTest limit. The smoke
used the production second-resolution wait for each injected operation and had
already taken 28.63 seconds in the current-source Windows Debug matrix.

The remediation adds a narrow injected clock for tests and embedders. Null
production requests retain the bounded system-clock wait. Injected timestamps
must remain valid and strictly advance the bound; a new negative assertion
proves a non-advancing clock refuses before provider apply. The 63-assertion
recovery smoke now passes locally in 1.78 seconds without changing its
30-second test limit. Independent non-authoring review passed after the clock
surface was narrowed to advancing timestamps only. Full hosted requalification
remains pending on the successor commit.

The final local Debug rebuild and complete 45-test native matrix passed after
that review in 13.29 seconds; the recovery smoke took 2.16 seconds within the
parallel matrix. The 36 focused Python contract/package/candidate tests and the
426-schema strict check also passed.
