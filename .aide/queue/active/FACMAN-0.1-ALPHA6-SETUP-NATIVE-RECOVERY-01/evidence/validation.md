# Validation

Source base: `412ab5aef55ecb771ee868ee46d1555d625de733`

Passed on 2026-09-13 against the current source and pinned Universal Setup and
Universal Launcher providers:

- MSVC Debug build of `facman_setup`,
  `facman_self_setup_recovery_smoke`, and
  `facman_windows_integration_ownership_smoke`.
- CTest selection
  `facman_self_setup_lifecycle|facman_self_setup_recovery_smoke|facman_windows_integration_ownership_smoke`:
  3/3 passed.
- Python selection `tests.test_self_setup_recovery_contract`,
  `tests.test_self_setup_package`, `tests.test_setup_package_routing`, and
  `tests.test_json_contract_subset`: 18/18 passed.
- `tools/codegen/generate_metadata.py --write` and
  `tools/project_state.py --write` completed.
- `tools/strict_check.py` passed with 418 registered schemas.
- `git diff --check` passed, apart from informational line-ending warnings.

The first strict run found one 345-character fixture line. It was reformatted
without changing behavior; the strict check then passed. The recovery smoke was
rebuilt and passed after adding real concurrent lock contention.

Independent model review first required changes for implicit rollback consent,
intent-scoped admission, canonical root aliases, unchecked durable writes,
timestamp bounds, provider-root persistence, terminal pre-apply retirement, and
schema/loader parity. Its final review then found that a portable journal could
inherit a later installed-mode adapter. Durable journal mode now controls native
reconciliation, the cross-mode restart regression passes, and the independent
review returned `PASS` on the corrected source.

PR #273 exposed a platform-specific defect in the contention fixture: the test
used the Windows case alias `INSTALL` for `install`, which names a different path
on case-sensitive Linux filesystems. The production root-lock implementation was
unchanged. The POSIX fixture now uses a directory-symlink alias to the same
existing parent. A local Ubuntu 24.04 GNU 13.3 build against the exact locked
providers passed `facman_self_setup_recovery_smoke` with 31 checks, and the
corresponding MSVC Debug CTest passed again on Windows. The failed hosted
observations remain run `34761848507`, jobs `103735973057` (`linux-native`) and
`103735973010` (`linux-coverage`); current hosted requalification is pending.
