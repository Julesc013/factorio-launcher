# Gate 2 local validation evidence

Validation date: 2026-07-21 (Australia/Sydney)

Branch baseline:

```text
branch: task/instance-spec-and-readiness-01
base: c10edae2bd3b6ffd95b476ed51ccdaf12ce3f2b0 (origin/dev)
scope commit: a2b851c
```

## Focused proof

```text
cmake --build build/gate2-local --target
  flb_factorio_instance_model_smoke facman_cli --config Debug -j 2
PASS

ctest --test-dir build/gate2-local -C Debug
  -R flb_factorio_instance_model_smoke --output-on-failure
PASS: 1/1

FACMAN_CLI_EXE=build/gate2-local/Debug/facman.exe
python -m unittest discover -s tests -p test_cli.py
  -k instance_projection -v
PASS: 1/1
```

The CLI test exercises both the ordinary direct client path and canonical
`facman rpc --stdio` bounded subprocess transport and requires equivalent
readiness payloads.

## Contract, architecture, and policy proof

```text
python tools/schema_validate.py
PASS: 261 schemas

python tools/codegen/generate_metadata.py
PASS: generated metadata current

python tools/command_contract_check.py
PASS: 125 commands

python tools/frontend_contract_check.py
PASS

python tools/application_handler_check.py
PASS

python tools/instance_model_check.py
PASS

python tools/refusal_contract_check.py
PASS: 217 codes

python tools/refusal_golden_check.py
PASS: 126 refusal goldens

python tools/strict_check.py
PASS

python .aide/scripts/aide_lite.py test
PASS

git diff --check
PASS
```

## Native and Python matrices

```text
cmake --build build/gate2-local --config Debug -j 2
PASS

ctest --test-dir build/gate2-local -C Debug --output-on-failure
PASS: 44/44

python tools/dev.py test --affected --base dev
  --build-root build/gate2-affected --configuration Debug
PASS: affected native/strict selection and 131 Python tests

python tools/dev.py test --full
  --build-root build/native-smoke --configuration Debug
PASS: full clean build and 360 Python tests; 7 intentional skips
```

The full run includes the Windows portable CLI package proof from the canonical
`build/native-smoke` location. The skips are existing optional frontend probes
whose binaries are not built by that profile; frontend command metadata and
transport truth validators passed independently.

An earlier raw `unittest discover` invocation against `build/gate2-local`
executed 338 tests and reported one setup error because the package test
requires `build/native-smoke/Debug/facman.exe`. This was an invocation-layout
error, not a product failure. It was superseded by the repository-owned full
runner above, which created the required canonical tree and passed all 360
tests.

## No-write and authority result

Tests compare workspace file inventories and SHA-256 digests before and after
repeated describe/readiness calls, including refusal and recovery cases. A
non-existent workspace remains absent. Installation and fixture bytes remain
unchanged. The new model contains no directory creation, durable output,
transaction begin, file copy/rename/removal, process-launch, network, Setup, or
credential primitive.

Every response reports:

```text
mutation_executed = false
preparation_executed = false
execution_started = false
permit_issued = false
credential_accessed = false
network_accessed = false
preparation_available = false
execution_available = false
```

## Reviewed integration proof

PR #39 merged reviewed implementation head
`fa11b056c03784964e66ef391a81a6dfa8fcedc1` at `dev`
`7113011a6c4fe1d76d4c09cc36bc8a3aafa34b36` after exact-head CI
`29812506939`, code-security `29812506919`, schema-check `29812506783`, and
security-policy `29812507063` passed.

The first isolated reproduction exposed an ancestor-path false negative in the
CMake architecture validator after every native build and CTest had passed.
PR #40 corrected only that path filter and added a regression test. Its exact
head `f5915475eff78c255fe1f618a8be12c9c0f2d0f9` passed CI `29814299428`,
code-security `29814299449`, and security-policy `29814299432`, then merged at
final `dev` `bbb46c5bfd10cd35fb965b23edc4951784f93ef4`.

The final exact-`dev` CI `29815159526`, code-security `29815159602`, and
security-policy `29815159595` passed. The dedicated schema workflow did not
retrigger for the path-only correction; the implementation merge passed it at
`29813605517`, while final CI strict validation and the clean reproduction both
revalidated all 261 schemas.

The evidence-only closeout branch reran the repository-owned full local matrix:
44/44 native tests and 361 Python tests passed with seven declared optional
frontend skips.

## Clean pinned reconstruction

```text
FacMan:             bbb46c5bfd10cd35fb965b23edc4951784f93ef4
Universal Launcher: 7bd4425f0c35414f738159b45d8bec42edf70235
Universal Setup:    3f8489275077347c2918f3bb03614ec6431362ff
result:             PASS
duration:           387.0 seconds
```

All repositories were detached and clean before and after validation. Both
providers and FacMan configured, built, tested, and passed strict checks;
FacMan also passed AIDE Lite and the complete Python suite. The isolated source
and build root was removed after proof capture.
