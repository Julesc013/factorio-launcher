# Validation

Machine preparation result: `PASS`.

- `cmake --build build/m2-wu9 --config Release --target usk_live_acceptance --parallel`
  in Universal Setup: PASS at exact main
  `3f8489275077347c2918f3bb03614ec6431362ff`.
- `usk_live_acceptance.exe --root D:\FacMan-Live-Acceptance\M2 --run-id
  m2wu10-20260715-01 --setup-revision 3f8489275077347c2918f3bb03614ec6431362ff
  --consumer-revision 384c2569c84696c5fce02802684e30fad44f9ee0 --confirm APPLY`:
  PASS; automated findings complete, operator verdict pending.
- `py -3 tools/m2_wu10_operator_acceptance_check.py --require-live-root`:
  PASS; summary, archive, four packets, retained tree, final roots, and
  authority boundary revalidated.
- `py -3 -m unittest tests.test_m2_wu10_operator_acceptance
  tests.test_aide_compaction tests.test_aide_target_truth`: PASS, 16 tests.
- `py -3 tools/schema_validate.py`: PASS, 231 schemas.
- `py -3 tools/source_format_check.py`: PASS.
- `py -3 tools/strict_check.py`: PASS.
- `ctest --test-dir build\m2-wu9 -C Release --output-on-failure`: PASS,
  41 of 41 native tests.
- `py -3 -m unittest discover -s tests -p "test_*.py"`: PASS, 345 tests
  with one intentional opt-in skip; the full suite completed in 415.455 s.
- `git diff --check`: PASS.

Hosted validation at exact revision
`980d5b9e3113a673782d6efde74291b0c477f14b` is complete:

- push CI `29364492582`: PASS;
- push CodeQL `29364492665`: PASS;
- push security policy `29364491886`: PASS;
- push schema check `29364492053`: PASS;
- draft PR #25 CI `29364494313`: PASS;
- draft PR #25 CodeQL `29364495679`: PASS;
- draft PR #25 security policy `29364495081`: PASS;
- draft PR #25 schema check `29364494922`: PASS.

The retained run contains 26 files, 14 directories, 40,105 bytes, zero
reparse points, four evidence packets, and five audit events. The current
moved target is removed; the pre-move root remains intentionally retained.

This validation does not create the human `Pass`, `Fail`, or `Inconclusive`
verdict.
