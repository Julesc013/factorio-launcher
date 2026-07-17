# Validation

Current result: M2 closeout candidate. Complete local validation passed;
hosted task-branch validation remains pending.

- focused closeout, target-truth, and release-structure tests: PASS, 16 tests.
- `py -3 tools/strict_check.py`: PASS, including all 234 schemas.
- `py -3 .aide/scripts/aide_lite.py test`: PASS.
- `ctest --test-dir build\m2-wu9 -C Release --output-on-failure`: PASS,
  41/41 native tests.
- `py -3 -m unittest discover -s tests -p test_*.py -v`: PASS, 350 tests
  with one expected opt-in skip.
- `py -3 tools/required_package_proof.py`: PASS, 14 package-runtime tests
  with zero skips from clean candidate `be98d991db470d2583eef36d16550f474fcfe38b`.
- `py -3 tools/repro_workspace_smoke.py --require-clean --build --python
  "py -3"`: PASS; clean three-repository configure, build, CTest, strict,
  AIDE, and Python matrix.

The accepted WU10 integration base is
`5250db1d17ac330f5ae0b672ccc7466431a1e4a2`. Hosted task-branch, exact-`dev`, canonical `main`,
exact-`main`, public-integration, and `dev` synchronization proofs are not yet
recorded.
