# Validation

Policy implementation result: complete local validation pass. No acceptance
result is recorded.

Completed focused checks:

- `py -3 tools/m2_wu10_machine_acceptance_check.py --policy-only`: PASS;
  frozen policy valid and no result recorded.
- `py -3 -m unittest tests.test_m2_wu10_machine_acceptance -v`: PASS, three
  tests including all twelve required negative controls.
- `py -3 -m unittest tests.test_aide_compaction tests.test_aide_target_truth
  tests.test_m2_wu10_machine_acceptance -v`: PASS, 18 tests.
- `py -3 tools/schema_validate.py`: PASS, 234 schemas.
- `py -3 tools/source_format_check.py`: PASS.
- `py -3 tools/structure_policy_check.py`: PASS.
- `py -3 tools/aide_target_truth_check.py`: PASS.
- `py -3 tools/strict_check.py`: PASS, including the policy-only verifier and
  the unchanged historical pending operator record.
- `py -3 .aide/scripts/aide_lite.py test`: PASS.
- `ctest --test-dir build\m2-wu9 -C Release --output-on-failure`: PASS,
  41/41 native tests.
- `py -3 -m unittest discover -s tests -p test_*.py`: PASS, 348 tests with
  one skip.
- `py -3 tools/required_package_proof.py`: PASS, 14 package-runtime tests with
  zero skips.
- `py -3 tools/repro_workspace_smoke.py --require-clean --build --python
  "py -3"`: PASS; clean three-repository configure, build, CTest, strict,
  AIDE, and Python matrix.

The earlier strict run reached every check but correctly failed after detecting
stale generated project state and the initially misplaced `contracts/release`
policy directory. Project state was regenerated and the policy moved to the
existing `contracts/policy` authority root. The corrected strict, portable
AIDE, native, Python, required-package, and clean-workspace reproduction runs
above are terminal passes. These validate PR A only; they do not evaluate a
fresh acceptance root or record `EvidencePass` or `MachinePass`.
