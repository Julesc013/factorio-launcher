# Validation

## Passed

- `py -3 -m unittest` focused identity/release set: 106 tests passed.
- `py -3 tools/repository_identity.py`: PASS.
- `py -3 tools/branch_policy_check.py`: PASS.
- `py -3 tools/aide_target_truth_check.py`: PASS.
- `py -3 tools/aide_queue_state_check.py`: PASS, zero known exceptions.
- `py -3 tools/aide_compaction_check.py`: PASS.
- `py -3 tools/source_format_check.py`: PASS.
- `py -3 tools/schema_validate.py`: PASS, 356 schemas.
- `py -3 tools/provenance_check.py`: PASS.
- `py -3 tools/release_resolution_check.py`: PASS, four targets and twelve records per target.
- `py -3 tools/source_closure_admission_check.py`: PASS.
- `py -3 tools/project_state.py --validate`: PASS after regeneration.
- `py -3 .aide/scripts/aide_lite.py test`: PASS.

## Bounded incomplete run

`py -3 tools/strict_check.py` exceeded the five-minute command window before producing a
terminal result. Its two surviving child processes were stopped. The affected validators
listed above were then run directly and passed. This timeout is not recorded as a strict
suite pass and does not substitute for the full promotion matrix.
