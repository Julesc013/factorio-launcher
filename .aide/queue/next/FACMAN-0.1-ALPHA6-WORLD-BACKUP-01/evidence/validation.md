# World backup validation in progress

Validated on 2026-09-25 from the dirty implementation branch based on
`9361ada9c502f0ce65e75cd11a20c7837beb569c`. This is local engineering
evidence; it is not an exact-head product candidate or integration proof.

- Windows Debug developer `facman_cli` and `fl_transaction_session_smoke` built
  under the marker-owned external task root
  `E:/Downloads/FACMAN_WORLD_BACKUP_2026-09-25/task-root`.
- `ctest --test-dir .../native-developer -C Debug -R
  fl_transaction_session_smoke --output-on-failure`: PASS, 1 native test.
- Windows Release product build and unsigned `windows_product_x64` package:
  PASS. Packaged `bin/facman.exe` SHA-256 is
  `e359085765e0259db381c1960bee5300f74aa67a898c1a88abb4c0de88c4133`.
- With `FACMAN_CLI_EXE` pointed to that packaged executable,
  `py -3 -m unittest discover -s tests -p test_save_transfer.py`: PASS,
  10 tests. The cases exercise ordinary CLI backup, owned destination refusal,
  lock refusal, partial-copy fault cleanup, same-bytes source replacement,
  killed-process journal recovery, and clean retry. Byte, digest, sidecar, and
  schema checks use independent fixture and filesystem observations.
- Two affected `test_cli.CliTests` backup/export and refusal cases run through
  the same packaged executable: PASS.
- Final `py -3 tools/strict_check.py`, `py -3 .aide/scripts/aide_lite.py
  test`, `py -3 tools/codegen/generate_metadata.py --check`,
  `py -3 tools/project_state.py --validate`, and
  `py -3 tools/generate_plan_views.py --check`: PASS after restoring the
  planned queue state.
- `git diff --check`: PASS.

Follow-up on the production run-lock path: launch creates and holds
`<instance>/locks/run.lock` during supervised execution
(`runtime/factorio/launch/flb_factorio_launch_plan.cpp`). Backup now checks
that path before staging and again before publication. The rebuilt Windows
Debug executable passed 11 focused save-transfer cases, including a run lock
created during staging, plus the same two affected CLI regression cases.
`py -3 tools/strict_check.py` passed after this change. A new packaged and
exact-head candidate result is still required for this follow-up.

One test invocation from `tests/` failed before test execution because
`tools` was absent from `PYTHONPATH`; rerunning from the repository root with
`PYTHONPATH=.;tests` passed both requested cases.

Run `36125970801/1` later passed its Windows, Linux, Intel macOS and six-asset
bundle jobs at head `73d67389`. The downloaded bundle verified locally and its
Windows portable CLI passed 11 save-transfer and two affected CLI cases. The
bundle manifest SHA-256 is
`0d78a71a236ebfca2837566a24dce56b21dc1be9d37d183e117688345e9caf1f`.

The full macOS portable Python suite for that head then found two public
journeys that select an existing destination outside the workspace:
`test_complete_non_execution_journey_across_live_transports` and
`test_local_content_and_save_lifecycle_is_descriptor_driven_and_replayable`.
Both failed with `save_backup_destination_unowned`. The current correction
keeps those selected paths under a pinned existing parent and no-clobber
publication. A clean-first Windows Release product build passed. Both affected
journeys, the two affected CLI regressions, and external-destination
interruption/recovery passed against that built executable. The focused
save-transfer run had one path-separator-only assertion failure; after fixing
that assertion, all 11 save-transfer tests passed. `py -3 tools/strict_check.py`
and generated-metadata checks passed. Current source still needs a clean
commit and exact-head hosted/package checks.

## 2026-09-26 exact-head publication correction

The branch now contains protected `dev` merge `3723abedf29d038eba05b8f035f857363fa32c1b`
and commit `07f00ece1a34203b93e07491c86486d0281d44d9` by ancestry.
Source correction `07ec71592add090bd01eea6895c595d326143418` fixes a
real POSIX gap found by product candidate `36173342608`: a renamed external
destination parent could receive the backup after the last pre-publication
check. That candidate failed its Linux save-transfer CTest and was cancelled;
it is not qualification. The correction revalidates the held source and parent
at the publication boundary. A test-only pause marker makes the parent-swap
case wait until that boundary, then asserts both the original and substituted
paths contain no published ZIP or sidecar and recovery rolls back safely.

- Windows Debug CLI: `cmake --build .../native-developer --config Debug --target
  facman_cli --parallel 8`, then `ctest --test-dir .../native-developer -C Debug
  --output-on-failure -R ^facman_save_transfer_product$`: PASS, 16 cases,
  including one POSIX-only skip.
- Ubuntu 24.04 WSL CLI with exact locked local provider checkouts: `cmake
  --build .../native-linux --target facman_cli --parallel 8`, then `ctest
  --test-dir .../native-linux --output-on-failure -R
  ^facman_save_transfer_product$`: PASS, 16 cases including the 2-second
  publication pause and parent swap.
- `py -3 tools/strict_check.py`, `git diff --check`, and AIDE compact commit
  check: PASS. The optional pause signal uses the existing base atomic writer,
  so the critical-I/O architecture check remains clean.
- [Product candidate 36175342699](https://github.com/Julesc013/factorio-launcher/actions/runs/36175342699)
  was dispatched at source correction `07ec7159`, then cancellation was
  requested before the evidence update. The final combined-head candidate
  still has to be run; this local evidence is not package qualification.
