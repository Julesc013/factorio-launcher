# Factorio Application Operations

This module owns typed Factorio operations registered with Universal Launcher.
The first slice covers install discovery/import/inspection, instance creation,
and launch-plan preview.

The CLI may construct requests and render results. It must not reimplement the
persistence or product semantics of commands migrated here.
