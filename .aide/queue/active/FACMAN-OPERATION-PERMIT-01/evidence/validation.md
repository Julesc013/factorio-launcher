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

The provider-proof and adversarial slices additionally pass locally:

- Clean Visual Studio 2022 x64 Debug configure/build with warnings as errors.
- Full native CTest: 47/47 passed, including the three-repository proof,
  permit core, Gate 2 instance model, and dormant launch-provider verifier.
- Full Python suite: 364 passed, 2 skipped.
- Strict policy: 268 schemas, 242 refusal codes, 125 commands, 123 routes,
  520 SPDX source files, and all architecture/security/parity checks passed.
- Standalone permit fuzz corpus over valid, malformed, duplicate-key, time,
  and resource inputs.
- Portable AIDE Lite self-test.
- `git diff --check`.

Clang is not installed locally, so the actual libFuzzer engine is pending the
hosted Linux job. The target and bounded 1,000-run CI invocation are present;
this file does not claim that hosted result before it exists.
