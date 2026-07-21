# Gate 2 changed-file evidence

## Scope

The implementation remains inside the amended
`FACMAN-INSTANCE-SPEC-AND-READINESS-01` path allowlist. It adds a bounded
read-only instance projection and does not add preparation, permit, execution,
credential, network, Setup apply, signing, or publication paths.

## Runtime and application boundary

- `runtime/factorio/instance/flb_factorio_instance_model.{h,cpp}` implements
  evidence collection and deterministic `InstanceSpec`, `InstanceBinding`,
  `InstanceReadiness`, and `InstanceView` encoding.
- `runtime/factorio/application/modules/instance_module.{h,cpp}` owns the two
  additive application routes.
- application types, decoding, admission, typed handlers, composition, and
  CMake wiring register `instances.describe` and `instances.readiness`.
- the existing `instances.inspect` route and
  `factorio.instance_inspection.v1` response contract remain unchanged.
- CLI dispatch accepts the optional explicit `--intent` value and uses `menu`
  when omitted.

## Contracts and generated surfaces

- two command contracts declare only `workspace_read`, no persistent mutation,
  and no process execution;
- two generated request schemas accept a typed instance ID and registered
  launch intent;
- nine Factorio schemas define launch intent, evidence dependencies, readiness
  dimensions, blockers, resources, spec, binding, readiness, and view;
- command indices, generated runtime catalog, request validation, help,
  completions, strings, TUI, WinForms, and AppKit catalogs were regenerated;
- frontend required/optional truth includes the two new backend commands with
  each frontend's existing implementation/stub/not-supported disposition.

## Tests and fitness checks

- `tests/native/flb_factorio_instance_model_smoke.cpp` proves deterministic
  read-only projection, menu semantics, compatibility separation, invalid
  configuration, absent workspace no-create behavior, and missing-install
  blockers;
- `tests/test_cli.py` proves direct and bounded RPC parity, digest
  reconstruction, JSON-schema validity, unchanged lifecycle inspection,
  zero-save/account semantics, unlocked-mod degradation, portable-spec
  stability under local drift, missing/incompatible locks, recovery precedence,
  unsupported-intent refusal, and byte-for-byte no-write behavior;
- four command goldens cover successful projections and common refusals;
- `tools/instance_model_check.py` enforces the portable/local schema split,
  exact command effects, compatibility law, no-authority constants, test
  anchors, and absence of mutation/process primitives;
- command, frontend, application-handler, and strict validator registries were
  extended without relaxing unrelated checks.

## Documentation and truth

- `docs/architecture/instance_model_and_readiness.md` is the implemented Gate 2
  contract;
- the canonical product-model and lifecycle references now distinguish the
  implemented read-only projection from the larger target architecture;
- project-state generated surfaces record 125 command contracts, 123
  registered routes, 261 schemas, and 217 refusal codes while keeping the
  WorkUnit active and all dangerous authority unavailable.

Generated-only files and line-ending-normalized worktree observations are kept
inside the repository. No external clone, copied project, or persistent
temporary directory was created.
