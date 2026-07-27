# Changed files

## Deterministic queue model

- `tools/aide_queue_records.py`
- `tools/aide_queue_state_check.py`
- `tools/aide_compaction_check.py`
- `.aide/scripts/aide_lifecycle.py`
- `.aide/scripts/aide_lite.py`

These surfaces now share one complete-record definition, ignore only truly
empty directories, reject partial or invalid records, detect duplicate task
identities, and compare the generated index with the filesystem projection.

## Project truth

- `tools/project_state.py`
- `release/index/project_status.v2.toml`
- generated project-state, roadmap, support, checkpoint, and README surfaces

The compact queue separates automated, operator-waiting, blocked, verified,
and planned states. Revision roles and scorecard evidence are explicit.

## Lifecycle records

- revalidation 01 was superseded before `prepare` and archived;
- seven verified tasks were reviewed, closed, and moved to immutable history;
- `FACMAN-PROJECT-STATE-DETERMINISM-01` is the sole current automated task.

## Tests

- `tests/test_aide_compaction.py`
- `tests/test_aide_target_truth.py`

The regression suite proves empty-directory byte parity, partial-record
failure, invalid lifecycle failure, index-drift failure, operator-wait and
supersession transitions, derived scorecard truth, explicit revision roles,
and the no-authority revalidation supersession boundary.
