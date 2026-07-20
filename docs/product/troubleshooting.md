# Troubleshooting

Start with:

```bash
facman doctor
facman installs scan
facman installs list
```

For a specific instance:

```bash
facman launch-plan <instance>
facman launch plan <instance>
facman run <instance>
```

`run` is dry-run only. `--execute` currently returns
`isolation_not_proven`; it is not an override. Review `launch-plan` output while
the real Factorio write-isolation proof remains outstanding.

## Host-environment repairs

Windows Sandbox, WSL, native Linux, macOS, Wine/Proton, privilege, restart,
graphics, and filesystem state are not Factorio installation ownership. The
planned host-environment workflow is specified in
[`host_environment_lifecycle.md`](../architecture/host_environment_lifecycle.md).

Until those commands and setup recipes are implemented, `facman doctor` must
not imply that it can change Windows features, registry policy, services, WSL
distributions, Linux packages, macOS bundles, or external managers. Any manual
workaround should record the exact evidence, effect, elevation/restart need,
verification, and rollback rather than recommending a generic subsystem reset.
