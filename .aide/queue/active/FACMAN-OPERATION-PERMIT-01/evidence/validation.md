# OperationPermit validation evidence

The contract-law slice passes:

- `py -3 tools/schema_validate.py`: 268 schemas.
- `py -3 tools/refusal_contract_check.py`: 242 refusal codes.
- `py -3 -m unittest tests.test_schema_tools tests.test_refusal_contract`.
- Strict validation through `tests.test_schema_tools`, including generated
  target truth after `py -3 tools/project_state.py --write`.
- `git diff --check`.

The permit-core slice additionally passes:

- MinGW GCC configure and `facman_operation_permit_smoke` build.
- `ctest -R ^facman_operation_permit_smoke$` with the matching compiler
  runtime first on `PATH`.
- 25 consecutive native smoke executions, including concurrent replay.
- RFC 4231 HMAC-SHA-256 vector, canonical input-order equivalence, strict
  envelope round trip, bare/digest-only rejection, non-consuming admission,
  atomic consumption, mutation, revocation, restart, wall-clock, monotonic,
  and structured safe-result cases.
- `tools/source_format_check.py`, `tools/cmake_architecture_check.py`, and
  `tools/code_security_check.py`.
- `tests.test_architecture_fitness` and `tests.test_capability_policy`.

Gate 2 closeout validation remains recorded independently in
`docs/release/checkpoints/gate2-instance-spec-and-readiness-closeout.md`.
