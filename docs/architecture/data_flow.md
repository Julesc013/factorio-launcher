# Data Flow

```text
Factorio discovery/policy content
  -> Factorio binding
  -> universal launcher command graph
  -> dry-run launch plan
  -> frontend report
```

Managed install operations flow through Universal Setup. GUI, TUI, daemon, CLI,
and Python prototype shells are presentation or compatibility layers only.
