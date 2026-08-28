# Validation

Result: `PASS` locally on 26 August 2026.

- `python tools/strict_check.py`: passed, including 373 schemas, 127 commands, 244 refusal codes, package/release contracts, source closure, v4 route, route packet, and all non-authorizing publication gates.
- `python -m unittest tests.test_factorio_2_1_14_release_route tests.test_windows_private_route_bundle`: 23 tests passed.
- `facman_release_route_permit_gate_smoke`: passed; missing, malformed, stale, wrong-context, replayed, concurrent, and crash-claimed permits dispatched zero processes.
- `facman_engineering_play_harness --self-test-menu-observer`: passed.
- CTest `facman_release_route_permit_gate_smoke` and `facman_engineering_play_menu_observer_smoke`: passed.
- `python tools/factorio_2_1_14_release_route_v4_check.py`: passed; two-phase topology, exact identities, and all authority false.
- `python .aide/scripts/aide_lite.py test`, queue-state, target-truth, and source-closure admission checks: passed.
- Frozen v3 route SHA-256 remained `242b1ce14ab6c8ae36706d97d5f4f19a05921524ca5aed2dca836499c8c55fd9`.
- Frozen v1 policy SHA-256 remained `3522068f75842a871f87096863b52e86b610730cdfc3e4fdd23b81bd8005ec73`.

The native build used the exact canonical ULK 1.9.1 and USK 1.0.0 provider worktrees. No Factorio executable or Windows Sandbox configuration was launched.
