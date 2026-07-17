# Validation

Current result: `EvidencePass`; `MachinePass` not recorded.

- Rebuilt the runner from Universal Setup revision
  `3f8489275077347c2918f3bb03614ec6431362ff`: PASS.
- Fresh lifecycle run `m2wu10-20260717-02`: runner PASS.
- Fresh interruption run `m2wu10-20260717-02-interruptions`: runner PASS.
- Accepted verifier/policy revision
  `26eb7056984b42859e377c1ffd0ffb7c80488078`: `EvidencePass`.
- Observation SHA-256:
  `fb0fcb58eec795d45a56cb48773d74ed74a38d4b14834a4921c1542310777181`.

Complete local candidate validation:

- `py -3 -m unittest tests.test_m2_wu10_machine_acceptance
  tests.test_aide_compaction tests.test_aide_target_truth -v`: PASS, 19 tests.
- `py -3 tools/strict_check.py`: PASS, including all 234 schemas and the
  unchanged no-result boundary.
- `py -3 .aide/scripts/aide_lite.py test`: PASS.
- `ctest --test-dir build\m2-wu9 -C Release --output-on-failure`: PASS,
  41/41 native tests.
- `py -3 -m unittest discover -s tests -p test_*.py -v`: PASS, 349 tests
  with one expected opt-in skip.
- `py -3 tools/required_package_proof.py`: PASS, 14 package-runtime tests
  with zero skips from a clean checkout.
- `py -3 tools/repro_workspace_smoke.py --require-clean --build --python
  "py -3"`: PASS; clean three-repository configure, build, CTest, strict,
  AIDE, and Python matrix.

Hosted candidate validation at exact revision
`ff883cd7b88dda07c0a336ced267cbe1f9f2746f`:

- push CI `29562177050`: PASS.
- push code-security `29562177030`: PASS.
- push security-policy `29562177062`: PASS.
- PR CI `29562194145`: PASS.
- PR code-security `29562194103`: PASS.
- PR security-policy `29562194153`: PASS.

The separate result record is `MachinePass`, SHA-256
`a4a00a3f77b394f988a71f9eaa86de3c9c9b74a4051d1c2e3ad38f60b9ad8efa`.
The final result head still requires independent exact-head hosted workflows
before PR #28 may merge.
