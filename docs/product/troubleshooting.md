# Troubleshooting

Start with:

```bash
factorio-launcher doctor
factorio-launcher installs scan
factorio-launcher installs list
```

For a specific instance:

```bash
factorio-launcher launch-plan <instance>
factorio-launcher run <instance>
```

`run` defaults to dry-run mode. Use `--execute` only after reviewing the launch
plan.
