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
  530 SPDX source files, and all architecture/security/parity checks passed.
- Standalone permit fuzz corpus over valid, malformed, duplicate-key, time,
  and resource inputs.
- Portable AIDE Lite self-test.
- `git diff --check`.
- Explicit entropy-source success and unavailable-source refusal; the strict
  validator rejects any `std::random_device` fallback in the permit core.

Clang is not installed locally, so the actual libFuzzer engine is pending the
hosted Linux job. The target and bounded 1,000-run CI invocation are present;
this file does not claim that hosted result before it exists.

The first hosted Linux-native attempt at PR #42 passed all 47 native tests and
then failed the changed-source clang-tidy coverage guard because the new
libFuzzer entry point existed only in the conditional fuzz build and therefore
had no normal-build compile command. The repair compiles that entry point in
the standalone corpus target as well, preserving the guard without an
allowlist; it also instruments the permit static library in the libFuzzer
configuration. Replacement hosted proof passed.

Final reviewed-head evidence for `5f9f122d6d3e95a006c44e46ba54c0927e9d288c`:

- PR #42 CI run `29825371714`: PASS, including Linux Debug/Release,
  clang-tidy, sanitized full CTest/corpus, bounded 1,000-run libFuzzer,
  coverage, Windows Debug/Release/WinForms/package reproducibility, macOS
  native/archive/AppKit/package proof, and all Python/strict checks.
- PR #42 code-security run `29825371722`: PASS for all configured languages.
- PR #42 schema-check run `29825371753`: PASS.
- PR #42 security-policy run `29825371793`: PASS.

PR #42 merged into `dev` at
`91c2aa4fe0a30be97bf16165b41a95a8fab4cd11`. Exact merged-`dev` runs:

- CI `29826221338`: PASS.
- code-security `29826221318`: PASS.
- schema-check `29826221373`: PASS.
- security-policy `29826221366`: PASS.

The final clean reproduction used one temporary root with detached, clean pins:

- FacMan `91c2aa4fe0a30be97bf16165b41a95a8fab4cd11`;
- Universal Launcher `7bd4425f0c35414f738159b45d8bec42edf70235`;
- Universal Setup `3f8489275077347c2918f3bb03614ec6431362ff`.

All three repositories configured, built, tested, and passed strict checks;
FacMan additionally passed AIDE Lite and its complete Python suite. The clean
run completed in 442 seconds and all three source worktrees remained clean.
An earlier attempt was inconclusive because a two-minute shell timeout left an
MSBuild child writing the interrupted build tree; restarting against that same
tree caused PDB contention. No product test failed. The final proof used a new,
single-writer build directory and passed.

The truth-only closeout transition additionally passes locally:

- `py -3 tools/project_state.py`;
- `py -3 tools/strict_check.py`;
- `py -3 .aide/scripts/aide_lite.py test`;
- full Python suite: 364 passed, 2 skipped;
- full native CTest: 47 of 47 passed;
- `git diff --check`.
