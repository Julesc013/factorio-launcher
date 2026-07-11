# Typed application handlers

Status: implemented locally for R3.4 WorkUnit 8.

The FLB application entrypoint is a composition and response-lifetime boundary.
`command_dispatch` is the only application module that accepts boundary JSON;
it decodes bounded documents into `ApplicationRequest`. `command_result` owns
the structured response envelope. Command-family handlers receive typed request
objects and an `ApplicationContext`; they never write to stdout or stderr.

`ApplicationContext` owns the workspace layout, typed repositories, clock, and
ID generator for one application lifetime. Domain archive and transaction
services remain narrow native modules rather than a generic filesystem mock.

Handlers are split by product, doctor, install, instance, launch, mod, modset,
save, diagnostic, recovery, setup, and unavailable capability families.
Product inspection, doctor, install/instance listing, run-execute refusal, and
setup refusal are registered application commands, so frontend code does not
invent a second backend result for those capabilities.

The strict application-handler check caps the composition entrypoint, requires
every family file, rejects JSON parsing and frontend output in handlers, and
requires the authoritative unavailable routes to remain present.
