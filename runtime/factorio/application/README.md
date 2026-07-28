# Factorio Application Operations

This module owns typed Factorio operations registered with Universal Launcher.
The C boundary decodes requests, applies global workspace, dry-run and
capability admission, looks up one static domain module, and writes the
frontend-neutral response envelope.

The module registry delegates every product command to one of:

- workspace and preferences;
- setup;
- installations;
- instances and transfers;
- profiles;
- Factorio content, snapshots and servers;
- recovery and migration;
- diagnostics and development refusals;
- launch planning and execution.

The CLI may construct requests and render results. It must not reimplement the
persistence or product semantics of commands migrated here.

The migrated slice decodes JSON once at this boundary into command-specific
request structures. Handlers do not search raw request text for field names.
The bounded decoder accepts only the string and string-array shapes used by
this slice, rejects duplicate or unknown fields and trailing data, and applies
payload resource limits. It is not a general JSON library; a vetted parser is
still required before network or richer third-party payloads are admitted.
