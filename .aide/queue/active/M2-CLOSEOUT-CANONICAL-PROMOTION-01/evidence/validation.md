# Validation

Current result: canonical M2 promotion and exact-main proof passed; the
public-integration record is locally validated and awaiting hosted review.

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
- closeout PR #29 exact-`dev`: PASS at
  `4afab65448831b05ab790957abf0e1798074ad1a`, runs `29567550655`,
  `29567550714`, and `29567550663`.
- promotion PR #30 exact head: PASS, runs `29568218139`, `29568218162`,
  `29568218137`, and `29568218125`.
- canonical `main`: PASS at
  `bd0642951a4a3abfb2cc1916c8b9c2c4e81d880f`, runs `29569007275`,
  `29569007270`, `29569007323`, and `29569007290`.
- public-integration record local rerun: PASS; strict checks with 234 schemas,
  AIDE Lite, 41/41 native tests, and 350 Python tests with one expected skip.

The accepted WU10 integration base remains
`5250db1d17ac330f5ae0b672ccc7466431a1e4a2`. The public-integration record's
hosted task-branch proof, independent `dev` merge, and post-promotion `dev`
synchronization remain pending.
