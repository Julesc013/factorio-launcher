# Native production-control gallery

Work item: FACMAN-0.1-ALPHA6-NATIVE-CONTROL-GALLERY-01.

The first slice renders the existing WinForms C1ShellForm. It includes the
ordinary pages, Launch Deck, refusal detail, native lists and buttons. There is
no second implementation of these product controls.

C1SnapshotProjection is the pure mapper used by both the live presentation
store and the gallery. It accepts backend-shaped scoped snapshots and an
explicit observation time. Unavailable projections start with empty data;
sample installation, instance, readiness and action records are never inherited.
Active operation records produce the running status. Existing five-state C1
evidence fixtures retain their separate historical representation.

An explicit C1GallerySession constructor selects the gallery boundary regardless
of FACMAN_PRESENTATION_MODE. The form constructs no live store or transport.
Ordinary, descriptor, settings, instance-selection and Advanced actions append
their identifiers to an in-memory recorder. They cannot change the fixed
projection, start a child explorer, invoke RPC, or request game/setup effects.
The window identifies this recording-only mode. Ordinary product startup still
uses its existing live backend path.

Run from the repository on Windows:

```powershell
python tools/native_control_gallery.py
python tools/native_control_gallery.py --show ready
python tools/native_control_gallery.py --show ready-overflow
```

The first command builds the production assembly and separate gallery host,
runs the automated cells and produces PNGs plus JSON receipts. The other
commands open the same production form for interactive inspection. All outputs
go beneath the marker-owned development task root reported by
`tools/workspace_hygiene.py paths`; no product build is created in the checkout.

The deterministic cases are ready, blocked, busy, recovery, empty and error,
plus a long Unicode identity and 41-row overflow case. Their inputs are produced
by tools/control_gallery_fixtures.py from the current production snapshot
schema's golden record. No fixture executes the action descriptors it carries.
The Python checks validate every scoped input against that schema.

The real-control harness checks the six distinct states, native UI Automation,
focus entry across every page, ancestor-visible control geometry, complete
overflow-row reachability, actual system-palette bindings and measured body-text
contrast. It activates buttons, including Advanced, and checks exactly one
recording per click, no live child form, and unchanged scenario identity. Long
Launch Deck labels retain their full text in accessible descriptions while
ellipsizing within their allocated space. Pages scroll when content exceeds
the available height; planning actions have their own full-width row.

The 100%, 125%, 150% and 200% cells use Control.Scale. Receipts identify that
simulation explicitly and record the actual system high-contrast flag. These
checks do not qualify monitor-DPI transitions, a high-contrast theme that was
not active, screen-reader usability or human experience. Those require separate
candidate-bound host observations. The gallery does not change the user's
system theme or display settings.

GTK remains the next slice of this WorkUnit: extract its production Launch
Deck renderer for shared use by a gallery target without command_client.c,
then run its existing native build and external AT-SPI/Orca checks against the
same scenario matrix. This Windows slice does not complete the WorkUnit or
claim Beta readiness.
