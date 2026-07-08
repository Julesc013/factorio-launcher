# Factorio Commands

Owns Factorio-specific command contract notes.

Examples:

- `factorio.product.inspect`
- `factorio.installs.scan`
- `factorio.installs.inspect`
- `factorio.instances.create`
- `factorio.launch.plan`
- `factorio.modsets.lock`

Do not define universal command graph mechanics here.

Every `*.v1.toml` descriptor must declare `effects = [...]` using
`contracts/policy/effects.v1.toml`. Effects are the stable risk vocabulary that
lets CLI, TUI, daemon, GUI, and tests agree on dry-run, workspace-write,
process-execute, network, credential, and setup-mutation behavior.
