# Presentation readiness observation

Launch Deck defaults to **Menu**. Selecting **Selected Save** refreshes readiness
for the exact save chosen by the instance profile. This choice observes the
current selection; it does not change the profile, save, settings or workspace.
Play remains unavailable for Selected Save until its separate execution authority
is implemented and qualified.

The existing presentation query and action routes accept optional `launch_intent`
(`menu` or `load_save`); their CLI accepts `--intent menu|load_save`. Omission means
`menu`. Unsupported and empty supplied values are refused. The effective intent
is included in `selected_context` and revision identity even without an instance.
Actions carry the intent of their source snapshot. A revision from another intent
is stale; replacement snapshots retain the requested observation intent. The
explicit menu launch preview continues to preview menu.

Menu action canonical requests retain their existing closed 20-field shape and
fingerprint. Selected Save adds only `launch_intent: "load_save"`. Durable receipt
readers accept these two exact shapes, with all existing digest and identity
checks retained. Reusing an idempotency identity with another intent conflicts;
legacy receipts and prior results are never rewritten. The GUI retains the exact
original payload when inspecting a transport-uncertain action, even after changing
its observation choice.

Native fixture tests and source checks do not qualify a real game, human journey,
other host, Beta admission or the active WorkUnit's remaining acceptance clauses.
