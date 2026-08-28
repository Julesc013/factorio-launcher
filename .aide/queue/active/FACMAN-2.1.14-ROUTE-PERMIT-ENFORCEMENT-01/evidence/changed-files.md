# Changed files

- `.aide/**`, `release/index/plan.v1.toml`, and generated project-state views reconcile completed, superseded, active, and future WorkUnits.
- `contracts/policy/factorio/windows_sandbox_play_2_1_14_base_windows_x64.v2.toml` and `release/index/successor_play_route.v4.toml` define the non-authorizing two-phase route.
- `contracts/schema/factorio/**` and `contracts/schema/release/**` define the v2 policy, v4 route, permit custody, readiness, issuance, consumption, refusal, freshness, and launch-one terminal contracts.
- `tests/native/facman_release_route_permit_gate.{h,cpp}` adds route-local HMAC decoding, validation, atomic one-time claim, and durable receipt behavior.
- `tests/native/facman_release_route_permit_gate_smoke.cpp` covers zero-dispatch refusal, replay, concurrency, crash-claim, and receipt failure cases.
- `tests/native/facman_engineering_play_harness.cpp` binds the complete route context and consumes the permit before process dispatch.
- `tools/windows_private_route_bundle.py` and `tools/windows_private_route_guest.ps1` enforce the five-mapping, complete-isolation, two-phase guest topology.
- `tools/factorio_2_1_14_release_route_v4_check.py` and related strict validators bind and verify the new route without granting execution authority.
- `tests/test_factorio_2_1_14_release_route.py`, `tests/test_windows_private_route_bundle.py`, and `tests/test_alpha_release_source.py` provide mutation and lifecycle regression coverage.
- Generated command/version projections and release documentation were refreshed after canonical plan reconciliation.

No product package, Factorio archive, frozen v3 route, or frozen v1 policy was modified.
