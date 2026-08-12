# Reconciliation validation

Recorded: 12 August 2026

## Exact source refs

- canonical fetched `origin/dev`:
  `4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f`
- synthesized branch head:
  `85648ff0bf0bef30b71bfb25a805c4082f144f9b`
- exact retained candidate head:
  `edc60b244a43c5a267078f2a7db5a45b2aa1d01b`
- reconciliation authority commit:
  `f92da63747324330a4e4a7718d3a0f9cbd7f2099`

## Authority assertions

- `source_closure_status = "deferred_external"`
- `source_closure_result = "not_run"`
- `current_valid_evidence = []`
- all three temporary route-index evidence gates: `false`
- Factorio execution, Setup mutation, qualification, route capability, route
  promotion, tags, signing, publication, release, and support authority:
  `false`

The canonical route refuses an evidence run before archive access. Synthetic
admission fixtures still prove that the three temporary fields must open and
close atomically.

## Validation results

- `python tools/source_closure_admission_check.py`: PASS
- `python tools/successor_play_route_definition_check.py`: PASS
- `python tools/project_state.py --validate`: PASS
- `python tools/schema_validate.py`: PASS, 337 schemas
- `python tools/package_check.py`: PASS, 26 manifests
- `python tools/release_programme_check.py`: PASS
- `python -m unittest tests.test_source_closure_admission`: PASS, 16 tests
- `python -m unittest tests.test_remote_source_closure`: PASS, 25 tests
- `python -m unittest tests.test_successor_play_route_definition`: PASS, 20 tests
- `python -m unittest tests.test_plan_views tests.test_current_truth_roles tests.test_aide_target_truth tests.test_aide_compaction`: PASS, 51 tests
- `cmake -S . -B build/native-smoke ... -DCMAKE_CXX_FLAGS=/EHsc`: PASS
- `cmake --build build/native-smoke --config Debug --parallel 4`: PASS
- `ctest --test-dir build/native-smoke -C Debug --output-on-failure`: PASS,
  38 of 38 tests
- `python -m unittest discover -s tests`: PASS, 976 tests, 13 skips
- `python tools/strict_check.py`: PASS

The pinned disposable validation clones matched the workspace lock exactly:

- ULK commit `1cafe4054297cc11e02458b83d230db0cd064471`, tree
  `47018102de4b9fd20af9f77acd4e1e35e51590f3`
- USK commit `32488fc13bd2439f9f6e52e83a97f6da345a7650`, tree
  `12fe757b1fc2ae78768a8cf912d03835f46ca65b`

## Classified attempts

The first sandboxed native configure failed because MSBuild FileTracker was
denied access. The unsandboxed retry found the compiler and then correctly
required explicit provider roots. The first provider build exposed MSVC C4530
under Visual Studio 18; reconfiguration with `/EHsc` passed without editing
provider source.

An initial full-discovery command used package-root semantics and produced
top-level test-helper import errors plus expected missing-build/provider
failures. It is superseded by the correct `discover -s tests` run above.

## Sync state

`git fetch origin --prune` succeeded. `gh auth status` reports an invalid token
for `Julesc013`; push, draft PR creation, and hosted-CI inspection have not run.
