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

Hosted cross-platform and exact-merged-`dev` evidence are intentionally not
claimed here; they belong to the reviewed PR and post-merge closeout sequence.
