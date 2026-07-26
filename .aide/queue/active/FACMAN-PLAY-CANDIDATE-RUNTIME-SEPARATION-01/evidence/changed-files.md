# Changed files

## Runtime and build graph

- `cmake/FacManOptions.cmake`
- `runtime/factorio/CMakeLists.txt`
- `runtime/factorio/launch/README.md`
- `tests/native/CMakeLists.txt`
- `tools/cmake_architecture_check.py`
- `tests/test_architecture_fitness.py`

These files split product runtime, candidate projection, observer,
classification, and verdict ownership into explicit targets and enforce the
product-package boundary.

## Project truth and documentation

- `release/index/project_status.v2.toml`
- `release/index/current_state.v1.toml`
- `tools/project_state.py`
- `tests/test_aide_target_truth.py`
- `tests/test_aide_compaction.py`
- `.aide/memory/project-state.md`
- `.aide/memory/project-state.v2.json`
- `README.md`
- `docs/roadmap.md`
- `docs/release/checkpoints/README.md`
- `docs/architecture/play-candidate-runtime-separation.md`

These files activate and describe the bounded separation WorkUnit and bind its
local validation without granting execution authority.

## WorkUnit lifecycle

- `.aide/queue/index.yaml`
- `.aide/queue/active/FACMAN-PLAY-CANDIDATE-RUNTIME-SEPARATION-01/**`
- `.aide/history/completion-baseline-2026-07-26/index.json`
- `.aide/history/completion-baseline-2026-07-26/FACMAN-TRANSPORT-OUTCOME-SEMANTICS-01/**`
- removed mutable
  `.aide/queue/active/FACMAN-TRANSPORT-OUTCOME-SEMANTICS-01/**`

The accepted transport WorkUnit moved from the mutable queue into immutable
history; this separation WorkUnit became the single active item.

## AIDE archive correctness

- `.aide/scripts/aide_lifecycle.py`
- `tools/aide_compaction_check.py`
- `tests/test_aide_compaction.py`

PowerShell and log evidence now use the archive's declared LF-canonical digest
law.
