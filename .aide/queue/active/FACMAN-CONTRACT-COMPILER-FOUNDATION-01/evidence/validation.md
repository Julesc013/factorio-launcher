# Validation

- PR #188 reviewed source head: `5560ebf14355da24a69d5cbc4b5365a581e806d5`.
- Hosted source-head checks: 13 of 13 successful before synchronization.
- Detached normal-merge rehearsal tree: `b5f68a99126e2a481afd416f3c7fe54b0b6ce1ce`.
- Rehearsed combined contract-set digest:
  `f6348f7c04f8175db2d105a4e41623c8db26bbaa56a7b99a2f1f8f8fdd1ff66d`.
- Deterministic contract and metadata generation/check modes pass.
- Contract, route-v4, WSB bundle, and CMake architecture tests pass: 36 tests.
- Full strict validation passes with 373 schemas, 127 commands, and 244
  refusal codes.
- Windows native `fl_json_core_smoke` and
  `facman_release_route_permit_gate_smoke` pass against exact canonical ULK and
  USK pins.
- Engineering and release route harnesses compile but were not executed.
- The policy-compliant rehearsal commit range and preview-only changelog
  validation pass.

This rehearsal does not replace the required exact-head validation after the
actual protected route merge and contract-branch synchronization.
