# Changed-file evidence

## Route truth

- `release/index/successor_play_route.v2.toml`
- `release/index/successor_play_route.index.v1.toml`
- `release/index/successor_play_route.v1.toml` remains unchanged

## Validation

- `.github/workflows/schema-check.yml`
- `tools/successor_play_route_definition_check.py`
- `tests/test_successor_play_route_definition.py`
- planning, current-truth, and AIDE regression tests

## Canonical and generated planning truth

- `release/index/plan.v1.toml`
- `release/index/project_status.v2.toml`
- `release/index/current_state.v1.toml`
- `.aide/memory/project-state.v2.json`
- `.aide/memory/project-state.md`
- generated README, roadmap, and todo surfaces

## Documentation and governance

- `docs/release/checkpoints/facman-successor-play-route-definition-02.md`
- `docs/release/checkpoints/README.md`
- target-local AIDE task, status, index, and evidence surfaces

The schema workflow path filter and commands now produce a dedicated exact-head
route-definition result. No runtime implementation, provider lock, workspace
lock, provider repository, route v1, PR #123, Factorio input, signing input,
or publication surface is changed.
