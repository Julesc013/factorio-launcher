# Validation

Result: PASS for the complete local product verification and focused
remediation gates. This is machine evidence only.

Canonical full command:

```text
py -3 tools/dev.py verify-all product
```

Exact result:

- provider revision verification: PASS;
- shared product build: PASS;
- independent static release build: PASS;
- native CTest: 41/41 PASS;
- WinForms .NET Framework 4.8 Release: 0 warnings, 0 errors;
- Python promotion suite: 1,463 run, 0 failures, 0 errors;
- skips: 2 optional, 5 unsupported, 2 not applicable, 0 required blocked,
  0 unknown, 0 historical-only;
- promotion obligation gate: PASS;
- strict check: PASS;
- resource pack: 600 entries, 2,233,690 bytes, content SHA-256
  `4c9802f155c24f289c4d005d06b55bf1769cd939dbce62321875d5a21817827d`,
  pack SHA-256
  `ce95c45eb588fae9c0baee6199624e64d90cb872e71b6ba9945126c86c9dc10b`.

Focused pre-transition validation also passed:

- metadata, census, plan-view, and project-state freshness;
- schema, source-format, engineering-quality, beta-readiness, release-programme,
  release-identity, alpha closeout, route-request, and source-closure checks;
- 176 affected Python tests.

Final post-transition validation passed after canonical project-state
regeneration:

- metadata, census, plan views, project state, AIDE queue/target/compaction,
  engineering quality, beta readiness, release programme, release identity,
  and source-format checks: PASS;
- lifecycle-focused Python tests: 143 PASS;
- `tools/strict_check.py`: PASS;
- AIDE validation and self-test: PASS.

AIDE validation retained two nonblocking warnings: the generated project-state
packet exceeds its advisory token target, and the portable-pack detector does
not recognize this repository's existing project-managed AGENTS section. They
do not invalidate repository truth or product verification and are retained in
remaining risks rather than hidden.

No real Factorio execution, live managed-install mutation, human acceptance,
signing, notarization, tagging, publication, or support action is part of this
evidence.
