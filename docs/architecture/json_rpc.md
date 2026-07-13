# Future Daemon Protocol and Current Machine Transport

The current interop layers are:

1. the direct C ABI transport;
2. bounded newline-delimited JSON over CLI stdio.

The stdio transport is command-granularity interop and is not JSON-RPC or a
daemon protocol:

```bash
facman --json installs.scan
facman --json instances.list
facman --json launch.plan --instance space-age-main
```

The local daemon is a future authority-gated layer for long-running operations
such as:

- download queues
- Mod Portal cache updates
- install verification progress
- server supervision
- exports and diagnostics

Possible daemon transports, once implemented and threat-modelled, are:

- Windows: named pipe
- macOS: Unix domain socket
- Linux: Unix domain socket

Any daemon protocol must be explicitly versioned and must define progress,
cancellation, recovery, authorization, and redacted logs. `facmand` and
`DaemonTransport` are currently unavailable and must not be advertised as
working IPC.
