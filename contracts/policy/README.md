# Policy Contracts

Owns machine-checkable policy notes that are broader than a single schema.

Examples:

- no bundled Factorio binaries
- no ownership bypass
- no Python product runtime
- no GUI-only behavior
- dry-run launch plans by default

## Hermetic standalone Play

`factorio/hermetic_standalone_play_2_0_77_windows_x64.v1.toml` freezes the
first real-Play candidate law. It defines the bounded
`factorio.hermetic_process_tree.v1` claim, exact Windows x64 standalone
candidate class, writable and protected resources, evidence and observation
requirements, interruption matrix, and human `Pass` / `Fail` / `Inconclusive`
criteria.

`tools/hermetic_play_policy_check.py` validates the component schemas, exact
closed sets, canonical policy digest, and false authority claims. The frozen
policy adds no command, issuer, process route, or runtime authority.

## Effects

`effects.v1.toml` is the shared risk vocabulary for command contracts. Every
command descriptor under `contracts/command/factorio/` must declare a non-empty
`effects = [...]` list using only those policy terms.

The important split is:

- `none`: pure inspection with no workspace, process, setup, network, or
  credential effect
- `workspace_read`: reads local product or FacMan workspace state
- `workspace_write`: writes FacMan workspace state, exports, logs, or audit data
- `process_execute`: starts a local process
- `network_read`: reads a remote service
- `credential_read`: reads secrets or tokens
- `setup_preview`: calls Universal Setup for a non-mutating plan/report
- `setup_mutation`: asks Universal Setup to mutate installed software state
- `foreign_owned_refusal`: refuses because setup authority is not allowed
