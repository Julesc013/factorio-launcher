# Validation

- Exact-root, parent-repository, Git-ignore, repository-marker, and non-reparse preflight: PASS.
- Universal Launcher inventory: 2,036 files, 971 directories, 54,373,312 bytes.
- Universal Setup inventory: 9,183 files, 3,246 directories, 3,016,733,351 bytes.
- Both exact roots sent to the Windows Recycle Bin: PASS.
- Both build roots absent afterward: PASS.
- Universal Launcher clean at `e78cc9f3a23f748130749ebe7241dbd1166f8b25`: PASS.
- Universal Setup clean at `3f8489275077347c2918f3bb03614ec6431362ff`: PASS.
- `python -m unittest tests.test_aide_compaction tests.test_aide_target_truth tests.test_release_structure`: PASS (18 tests).
- Raw unconfigured unittest discovery: NOT APPLICABLE; it correctly could not find the now-absent default in-repository package binary.
- `python tools/dev.py test --full --build-root <retained-proof-build> --configuration Debug`: PASS (53 native tests; 487 Python tests; 29 intentional skips).
- `python .aide/scripts/aide_lite.py test`: PASS.
- `python tools/strict_check.py`: PASS.
