# Servers And Developer Tools

FacMan now exposes the first server and developer-tool command surfaces without
starting Factorio processes.

Implemented server commands:

- `facman servers create <name> --instance <instance-id>`
- `facman servers list`
- `facman servers start <server-id>`
- `facman servers stop <server-id>`
- `facman servers rcon <server-id>`

`create` and `list` manage local server profiles. `start`, `stop`, and `rcon`
return structured refusals until process supervision and RCON safety are
implemented.

Implemented developer commands:

- `facman dev bug-report`
- `facman dev dump-data`
- `facman dev dump-icons`
- `facman dev benchmark`
- `facman dev instrument-mod`

`bug-report` returns local FacMan workspace counts and redaction posture.
Execution-based developer tools return structured refusals until the launch and
instrumentation contracts are mature enough to run Factorio safely.
