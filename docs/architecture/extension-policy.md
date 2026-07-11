# Extension policy

Extend the narrowest owning module and preserve dependency direction. New
Factorio behavior belongs under `runtime/factorio`; reusable storage, platform,
archive, transaction, package, or core behavior belongs in its corresponding
runtime module. New presentation belongs under `apps/` and uses
`runtime/client`.

Extensions are contract-first: define command, schema, refusal, compatibility,
and claim impact before runtime code. Reuse generated metadata, typed IDs,
`Result`, platform I/O, repositories, and transaction sessions. Do not add a
second JSON parser, path-safety layer, package locator, journal, backend inside
a frontend, or source registry beside the existing authority.

Dynamic plugins, networking, credentials, setup mutation, and publisher trust
need separate reviewed WorkUnits. They are not enabled by creating an
interface or fixture.
