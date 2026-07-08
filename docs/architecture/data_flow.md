# Data Flow

```text
Factorio discovery/policy content
  -> Factorio binding
  -> universal launcher command graph
  -> dry-run launch plan
  -> frontend report
```

Managed install operations flow through Universal Setup. GUI, TUI, daemon, and
CLI shells are presentation layers only; they must not own setup mutation,
Factorio discovery law, mod resolution, or launch-plan generation.
