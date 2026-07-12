# Task OS Report-Only Commands

X-OS-01 adds local, report-only inspection and planning commands for AIDE Task OS records. These commands read the AIDE source repository's queue, status, evidence, and generated report files, then write deterministic reports under `.aide/reports/task-os-*`.

The inspection and planning commands do not execute tasks, apply repair plans, requeue work, create branches, merge, push, promote, publish releases, call providers or models, call the network, or mutate target repositories. The R3.5 wave lifecycle commands described below only mutate target-local coordination state under `.aide/memory/waves/` and its generated reports.

## Command Surface

- `py -3 .aide/scripts/aide_lite.py task status`
- `py -3 .aide/scripts/aide_lite.py task classify`
- `py -3 .aide/scripts/aide_lite.py task repair-plan`
- `py -3 .aide/scripts/aide_lite.py task requeue-plan`
- `py -3 .aide/scripts/aide_lite.py task resume-plan`
- `py -3 .aide/scripts/aide_lite.py blocker status`
- `py -3 .aide/scripts/aide_lite.py blocker classify`
- `py -3 .aide/scripts/aide_lite.py wave status`
- `py -3 .aide/scripts/aide_lite.py wave plan`
- `py -3 .aide/scripts/aide_lite.py wave create`
- `py -3 .aide/scripts/aide_lite.py wave next`
- `py -3 .aide/scripts/aide_lite.py wave start`
- `py -3 .aide/scripts/aide_lite.py wave verify`
- `py -3 .aide/scripts/aide_lite.py wave close`
- `py -3 .aide/scripts/aide_lite.py wave resume`
- `py -3 .aide/scripts/aide_lite.py wave archive`
- `py -3 .aide/scripts/aide_lite.py checkpoint status`
- `py -3 .aide/scripts/aide_lite.py checkpoint plan`

## Generated Reports

- `.aide/reports/task-os-command-status.md`
- `.aide/reports/task-os-task-status.md`
- `.aide/reports/task-os-task-classification.json`
- `.aide/reports/task-os-task-classification.md`
- `.aide/reports/task-os-repair-plan.md`
- `.aide/reports/task-os-requeue-plan.md`
- `.aide/reports/task-os-resume-plan.md`
- `.aide/reports/task-os-blocker-status.md`
- `.aide/reports/task-os-blocker-classification.json`
- `.aide/reports/task-os-blocker-classification.md`
- `.aide/reports/task-os-wave-status.md`
- `.aide/reports/task-os-wave-plan.md`
- `.aide/reports/task-os-checkpoint-status.md`
- `.aide/reports/task-os-checkpoint-plan.md`
- `.aide/reports/task-os-next-plan.md`

## Interpretation

`task status` summarizes known queue items and writes the task status report. `task classify` classifies the latest task packet into the X-OS-00 lifecycle vocabulary and records blockers or warnings as report data.

`blocker status` and `blocker classify` convert visible blocked, review-gated, or deferred state into typed report records. A repairable marker means "candidate for a future reviewed repair WorkUnit"; it is not proof that a repair was executed.

`task repair-plan`, `task requeue-plan`, and `task resume-plan` are planning aids. They may name suggested repair or resume paths, but they always record that no queue mutation, repair execution, target resume, or target mutation was applied.

`wave plan`, `checkpoint status`, and `checkpoint plan` retain the historical report-only Task OS planning surface. When a graph exists under `.aide/memory/waves/`, `wave status` projects that graph and writes a compact active-context report without loading closed history.

## Resumable Wave Lifecycle

The graph-backed lifecycle uses `aide.wave.v1` state. Every WorkUnit declares dependencies, provider revisions, allowed and forbidden paths, affected targets and tests, claim impacts, stop conditions, status, blockers, and its last green commit.

- `wave create` creates a target-local graph from `--manifest` or a minimal one-WorkUnit template. Existing state is preserved unless `--force` is explicit.
- `wave next` selects an already active WorkUnit or the first pending WorkUnit whose dependencies are closed.
- `wave start` makes exactly one dependency-ready WorkUnit active.
- `wave verify --test-result NAME=PASS` records supplied results, source/test fingerprints, Python toolchain identity, and provider pins. It does not run arbitrary commands and records that target-runner evidence was not inferred.
- `wave close` requires passing verification and no unrelated worktree changes. It records the exact `HEAD`, clean status, fingerprints, provider pins, remaining WorkUnits, and blockers.
- `wave resume` reads the last green checkpoint and next WorkUnit without loading archived history.
- `wave archive` accepts only a complete wave and writes a new immutable, commit-addressed history file. It does not overwrite an existing archive.

The validation cache is explicitly advisory. Cache entries have `promotion_eligible: false`; promotion cannot use cached proof alone, changed sources produce a new fingerprint, and local execution never manufactures target-runner evidence. Claim-impact rows are selection aids only and are never promoted automatically.

X-OS-02 adds a separate `capability` command group for capability reality scans, ledgers, overclaim reports, and validation. Those commands write `.aide/reports/capability-*` outputs and preserve the same report-only boundary.

## Boundary

Every report-only Task OS Markdown report includes these boundary markers:

- `mode: report_only`
- `task_execution: false`
- `repair_execution: false`
- `branch_mutation: false`
- `target_mutation: false`
- `provider_or_model_calls: none`
- `network_calls: none`

JSON classification reports include the same boundary under `no_apply_boundary`.

Wave lifecycle state changes are limited to `.aide/memory/waves/` and generated wave reports. They never execute the WorkUnit, mutate branches or targets, call providers/models/network services, promote a claim, or satisfy a human gate.

## Validation

X-OS-01 is covered by:

- `.aide/scripts/tests/test_x_os_01_task_os_commands.py`
- `.aide/scripts/tests/test_x_os_02_capability_reality.py` for the X-OS-02 capability surface
- `.aide/scripts/tests/test_r35_wave_autonomy.py` for graph validation, lifecycle ordering, checkpoint resume, failed-verification blocking, cache boundaries, and archive refusal
- `validate_task_os_command_files` inside `.aide/scripts/aide_lite.py`
- `validate_capability_files` inside `.aide/scripts/aide_lite.py`
- six `task_os_*` golden tasks added for command surface, status/classification, repair/requeue/resume planning, blocker classification, wave/checkpoint planning, and no-apply boundaries
- six `capability_*` golden tasks added for seed coverage, command surface, ledger generation, overclaim reporting, no-apply boundaries, and export-pack inclusion

The command reports are source-repository evidence only. Target repositories must generate their own status, blocker, wave, checkpoint, and capability-reality evidence after import.
