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
