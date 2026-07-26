# Validation

Date: 2026-07-26

Result: PASS for local implementation and promotion validation.

## Target ownership

- `facman::launch_planning` owns launch-plan and permit construction.
- `facman::product_execution` owns the product execution route.
- `facman::candidate_policy` owns candidate manifest/policy construction.
- `facman::candidate_projection` owns candidate projection.
- `facman::play_observer`, `facman_play_evidence_classification`, and
  `facman_gate4c_verdict_harness` are operator evidence targets gated by
  `FACMAN_BUILD_PLAY_EVIDENCE_TOOLS`.
- `flb_factorio_launch_static` remains an interface-only compatibility
  aggregate.
- The product model links planning and product execution, but does not link
  candidate, observer, classification, or verdict targets.

## Product-only package proof

Configured with:

```text
FACMAN_BUILD_TESTS=OFF
FACMAN_BUILD_PLAY_EVIDENCE_TOOLS=OFF
FACMAN_BUILD_TUI=ON
```

Exact `facman_cli` and `facman_tui` targets built and installed successfully.
No observer, evidence-classification, or verdict-harness target was generated.
No observer library, verdict executable, or evidence-orchestration Python tool
was installed. Historical documentation and schemas remain installed as
non-executable product documentation/contracts.

## Automated validation

```text
cmake --build build/presets/dev-windows --config Release
PASS

ctest --test-dir build/presets/dev-windows -C Release --output-on-failure
PASS: 54/54

python tools/cmake_architecture_check.py
PASS

python -m unittest -v \
  tests.test_architecture_fitness \
  tests.test_aide_target_truth \
  tests.test_aide_compaction
PASS: 20/20

python tools/test_obligations.py --profile promotion --evidence <active-evidence>
PASS: 517/517
required_blocked: 0
unknown: 0
optional: 2
unsupported: 2

python tools/project_state.py
PASS

python tools/aide_compaction_check.py
PASS
```

The two optional skips are the unbuilt WinForms package lane and the
opt-in full-scale R3.7 performance corpus. The two unsupported skips are
Windows environments where test symlink creation is unavailable. None is a
required or unknown obligation.

## Semantic preservation

- Hermetic policy digest remained
  `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`.
- Windows instance-isolated policy digest remained
  `8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432`.
- Existing candidate, plan, packet, resource-set, negative-control, and
  Pass/Fail/Inconclusive tests passed without semantic source changes.
- No Factorio process was started.
- No permit was issued.
- No public Play route, authority, policy, signing, or publication state was
  promoted.

## Incidental repair

Archiving the preceding WorkUnit exposed platform line-ending defects in AIDE
history hashing: `.ps1` was omitted by the writer, while `.log` was omitted by
both writer and validator despite Git treating the promotion logs as text. The
lifecycle writer and validator now canonicalize both extensions under
`text_lf_v1`, and regression coverage proves CRLF/LF independence. The archived
evidence files themselves were not changed.

The defect was reproduced by both exact-head CI events:

- push CI run `30211116812`;
- pull-request CI run `30211132683`.

Linux and macOS each passed their native build/test stages before failing the
same Python compaction assertion for the two archived promotion logs. The repair
was then validated locally by the focused compaction suite and the complete
strict validator before publication of the corrected revision.
