# Factorio Application Operations

This module owns typed Factorio operations registered with Universal Launcher.
The first slice covers install discovery/import/inspection, instance creation,
and launch-plan preview.

The CLI may construct requests and render results. It must not reimplement the
persistence or product semantics of commands migrated here.

The migrated slice decodes JSON once at this boundary into command-specific
request structures. Handlers do not search raw request text for field names.
The bounded decoder accepts only the string and string-array shapes used by
this slice, rejects duplicate or unknown fields and trailing data, and applies
payload resource limits. It is not a general JSON library; a vetted parser is
still required before network or richer third-party payloads are admitted.
