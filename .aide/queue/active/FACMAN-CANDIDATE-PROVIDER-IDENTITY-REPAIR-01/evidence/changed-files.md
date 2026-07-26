# Changed files

- `runtime/factorio/instance/flb_factorio_candidate_projection.cpp`
  now consumes generated provider revisions for both candidate routes.
- `runtime/factorio/CMakeLists.txt` exposes the generated identity privately to
  candidate projection.
- `tests/native/flb_factorio_launch_permit_smoke.cpp` asserts both route
  projections carry the generated ULK and USK identities.
- `tests/native/CMakeLists.txt` exposes the generated identity to that test.
- `tools/instance_isolated_play_candidate_check.py` rejects historical
  revision literals and requires generated-identity anchors.
- AIDE queue/evidence and generated project-truth surfaces record the repair.
