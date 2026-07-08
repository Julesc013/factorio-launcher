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

`run` defaults to dry-run mode. Use `--execute` only after reviewing the launch
plan. Execution uses the instance-local config and mod directory and records a
launch history entry under the instance logs directory.
