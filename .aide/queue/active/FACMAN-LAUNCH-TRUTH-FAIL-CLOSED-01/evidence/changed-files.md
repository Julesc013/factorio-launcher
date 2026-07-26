# Changed files

The bounded WorkUnit changes only the declared launch-truth, application
admission, installation-reference contract, candidate-storage marker,
player-message, documentation, test, validator, and AIDE coordination
surfaces.

Runtime and contract changes:

- `contracts/schema/factorio/factorio_install_ref.v1.schema.json`
- `runtime/factorio/application/application_configuration.cpp`
- `runtime/factorio/application/application_configuration.h`
- `runtime/factorio/application/command_admission.cpp`
- `runtime/factorio/application/command_admission.h`
- `runtime/factorio/application/flb_factorio_application.cpp`
- `runtime/factorio/application/handlers/launch.cpp`
- `runtime/factorio/application/modules/application_module.h`
- `runtime/factorio/application/modules/content_module.cpp`
- `runtime/factorio/application/modules/content_module.h`
- `runtime/factorio/application/modules/launch_module.cpp`
- `runtime/factorio/application/modules/launch_module.h`
- `runtime/factorio/discovery/flb_factorio_discovery.h`
- `runtime/factorio/instance/flb_factorio_instance_model.cpp`
- `runtime/factorio/launch/flb_factorio_hermetic_candidate.cpp`
- `runtime/factorio/launch/flb_factorio_launch_plan.cpp`
- `runtime/factorio/launch/flb_factorio_launch_plan.h`

Documentation and validation changes:

- `docs/architecture/application-module-composition.md`
- `docs/architecture/execution_foundation.md`
- `docs/architecture/hermetic_standalone_play_candidate.md`
- `docs/architecture/installation_model_and_reconciliation.md`
- `tests/golden/commands/instances.describe.success.json`
- `tests/golden/commands/instances.readiness.success.json`
- `tests/native/facman_application_types_smoke.cpp`
- `tests/native/facman_isolation_lock_smoke.cpp`
- `tests/native/m1_three_repository_system_proof.cpp`
- `tests/test_cli.py`
- `tests/test_end_to_end_user_journey.py`
- `tests/test_instance_isolation_probe.py`
- `tests/test_structure_policy.py`
- `tools/application_handler_check.py`

Coordination changes close the already-merged remote-source-closure WorkUnit
and activate this WorkUnit. No policy, permit, route, capability, writable-root,
Setup-authority, network-authority, credential-authority, publication, or
signing artifact changes.
