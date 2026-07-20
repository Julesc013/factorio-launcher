# Validation

Current result: PASS. Canonical M2 promotion, public integration, and
post-promotion `dev` synchronization are complete and exact-head proven.

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

The public-integration task revision
`44687765815174db8afc1da6fa768f7a655a6290` passed six push/PR workflows and
merged through PR #31 at `1678cb6d3c9545f09c4ae729054f68cf0fbc7bf2`.
That exact `dev` merge passed `29571806755`, `29571806753`, and `29571806738`.

The ancestry-only synchronization task revision
`6fb4a0c96503f32ad9070a5c557f2fa1a31209c8` preserved tree
`8487c87a097395186cccbcd13d929dd88d3b16fa`, made canonical `main` an ancestor,
and passed six push/PR workflows. PR #32 merged it at
`51977de8120202958fc35776d284077b1fc027d3`; exact synchronized-`dev` CI
`29573335555`, code-security `29573335458`, and security-policy `29573335488`
all passed.

The final closure-state rerun passed strict validation with all 234 schemas,
AIDE Lite, and all 350 Python tests with one expected opt-in skip.
