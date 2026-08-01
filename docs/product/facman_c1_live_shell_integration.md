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
or exact blocker, Activity, Last Run, and recovery are rendered from those
records. A changed readiness digest invalidates the cached view before Play.
The frontend does not retry. It dispatches only the exact generated
`run.execute` route, and only after a fresh backend readiness response says
`execution_available = true`; backend admission remains final.

Last Run persistence is deliberately non-authoritative. A shell may retain a
view copy only after receiving a complete `factorio.launch_session.v1` record.
The copy is bound to the workspace/readiness digest, is discarded when that
evidence changes, and cannot turn frontend termination into an exit outcome.
Incomplete backend journals always supersede the view copy and appear as an
explicit inspect/recover path. Recovery never auto-launches.

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
support lanes. Windows remains the supported C1 reference lane, but live Play
and release claims remain unavailable until their existing gates provide
evidence and authority.
