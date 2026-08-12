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

The local service is a future authority-gated lifecycle and transport host for
measured needs such as:

- download queues
- Mod Portal cache updates
- install verification progress
- server supervision
- exports and diagnostics

Possible daemon transports, once implemented and threat-modelled, are:

- Windows: named pipe
- macOS: Unix domain socket
- Linux: Unix domain socket

If admitted, the preferred product surface is `facman service run` using the
same terminal host artifact, not a required second `facmand` implementation.
Platform registration may point at that exact executable. The service hosts the
same application/presentation and frontend-session contracts; it owns no
independent product store, readiness, Last Run, setup, execution, credential,
or remote-control authority.

Any service protocol must be local-only by default, explicitly versioned, and
must define peer identity, permissions, bounded messages, capability
negotiation, subscriptions, progress, backpressure, cancellation, restart
recovery, abuse limits, compatibility, and redacted logs. `facmand`, service
mode, and `DaemonTransport` are currently unavailable and must not be
advertised as working IPC. Admission triggers and proof are defined in
[`unified_interaction_platform.v1.md`](unified_interaction_platform.v1.md).
