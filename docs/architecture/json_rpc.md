# JSON-RPC and CLI JSON Mode

Interop layers are added in this order:

1. CLI JSON mode
2. local launcher daemon
3. direct C ABI

CLI JSON mode is command-granularity interop:

```bash
facman --json installs.scan
facman --json instances.list
facman --json launch.plan --instance space-age-main
```

The daemon is for long-running operations:

- download queues
- Mod Portal cache updates
- install verification progress
- server supervision
- exports and diagnostics

Daemon transport:

- Windows: named pipe
- macOS: Unix domain socket
- Linux: Unix domain socket

Use JSON-RPC 2.0-style messages with schema versions, progress events, cancel
tokens, and redacted logs.
