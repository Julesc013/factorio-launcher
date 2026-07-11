# Factorio Effective Configuration

FacMan passes one instance-owned `config.ini` directly through Factorio's
`--config PATH` option. That file, not a sibling `config-path.cfg`, is the
effective configuration authority for the launch plan.

The generated \`[path]\` section contains absolute paths:

```ini
[path]
read-data=<selected Factorio install>/data
write-data=<FacMan workspace>/instances/<instance-id>
```

The launch plan also passes `--mod-directory` for the instance `mods/` root.
Saves and script output derive from `write-data`; the log root is treated as
that same write root for isolation accounting.

This decision follows the Factorio Wiki command-line reference, which defines
`--config` as the config file to use, and the application-directory reference,
which documents `read-data` and `write-data` in `config.ini` and identifies
`write-data` as the user-data location:

- <https://wiki.factorio.com/Command_line_parameters>
- <https://wiki.factorio.com/User_data_directory>

FacMan therefore does not modify an install-owned `config-path.cfg`, which may
be overwritten by Steam or package updates. Preflight parses the exact
`config.ini` passed in the argument vector and refuses missing, malformed,
relative, tokenized, mismatched, default/global, install-overlapping, linked, or
reparse-crossing roots.

## Proof Boundary

The test probe proves argument transfer, effective-config parsing, protected
directory invariance, intended writes, and per-instance lock behavior across a
real process boundary. It does not emulate or prove Factorio's internal path
implementation. Real Factorio isolation remains unproven until the
operator-supplied smoke procedure passes and its evidence receives a human
verdict.
