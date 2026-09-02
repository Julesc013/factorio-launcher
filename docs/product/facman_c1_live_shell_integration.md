# FacMan C1 live shell integration

The WinForms reference shell and the AppKit/GTK preview shells now start in
live-backend mode. Their product surfaces are projections of existing FacMan
records returned through `facman.transport_request.v2` / bounded `rpc --stdio`.
No shell owns discovery, readiness, route admission, process lifetime, or
recovery policy.

The bounded read sequence is:

```text
workspace.status
→ installs.scan
→ instance.list
→ selected instances.inspect
→ selected instances.readiness
→ workspace.recovery.inspect
```

The selected instance and installation summaries, readiness, available action
or exact blocker, and recovery are rendered from those records. Activity and
Last Run are separate typed projections: the ULK session journal is the sole
live Last Run authority, and `presentation.query` is the product read seam.
The WinForms reference shell consumes that projection. The compatibility
AppKit and GTK shells report authoritative Last Run as unavailable until they
adopt the same typed query; they do not infer it from the bounded read sequence.
A changed readiness digest invalidates the action view before Play. The
frontend does not retry. It dispatches only the exact generated
`run.execute` route, and only after a fresh backend readiness response says
`execution_available = true`; backend admission remains final.

A frontend may hold a transient non-authoritative view copy only after the
backend projects a complete `factorio.launch_session.v1` record. Such a copy
is never persisted or consulted as authority or fallback, cannot manufacture
a terminal outcome, and is discarded when its workspace/revision binding
changes. Missing, incomplete, corrupt, incompatible, uncertain, or recovery-
required backend state remains explicit. Recovery never auto-launches.

The GTK projection helpers bound semantic lookup to the transport `payload`
or `error` object. The transport envelope's own `schema` therefore cannot be
mistaken for a completed launch-session schema. A Meson/GLib regression runs
the generated helper against that exact envelope ordering in CI.

Set `FACMAN_PRESENTATION_MODE=evidence` to enter the explicitly labelled
evidence/development mode. It uses the existing deterministic fixtures without
changing their bytes. This mode grants no Play, route, permit, promotion,
qualification, support, signing, or publication authority.

This integration adds no daemon, direct client, transport, service protocol,
provider pin, route, or Universal Launcher ABI. AppKit and GTK remain preview
candidate lanes. Windows remains the C1 reference-candidate direction, but this
design classification grants no support authority. Live Play and release claims
remain unavailable until their existing gates provide evidence and authority.
