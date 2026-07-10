# Factorio Commands

Owns Factorio-specific command contract notes.

Examples:

- `factorio.product.inspect`
- `factorio.installs.scan`
- `factorio.installs.inspect`
- `factorio.instances.create`
- `launch_plan.build`
- `launch_plan.preflight`
- `run.preview`
- `factorio.modsets.lock`

Do not define universal command graph mechanics here.

Registry descriptors use canonical IDs. User-facing aliases are declared by
frontend contracts and normalized before Universal Launcher invocation.

Every `*.v1.toml` descriptor must declare `effects = [...]` using
`contracts/policy/effects.v1.toml`. Effects are the stable risk vocabulary that
lets CLI, TUI, daemon, GUI, and tests agree on dry-run, workspace-write,
process-execute, network, credential, and setup-mutation behavior.
