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

The GTK slice shares shell_view.c between the ordinary FacMan executable and
the facman-control-gallery Meson target. The production controller keeps its
existing live backend and historical explicit evidence paths. Its menus,
five pages and Launch Deck now use the same view and presentation record as
the gallery. The gallery links only that view and its recording host; it has
no command_client.c, RPC controller or process-spawning implementation.
Advanced and ordinary action buttons all use the injected recorder.

On a Linux GTK 3 host with Meson, Xvfb, D-Bus and Python GI/AT-SPI installed,
run against an existing marker-owned task root:

```sh
python3 tools/gtk_control_gallery.py --task-root /path/to/owned/task-root
python3 tools/gtk_control_gallery.py --task-root /path/to/owned/task-root --cases ready-overflow --scales 200 --themes HighContrast
```

The runner verifies source ownership and the Meson warnings-as-errors setting,
builds both executables, runs the existing native Meson tests and starts an
isolated Xvfb/D-Bus session. It supports an existing Windows-owned task root
mounted through WSL without rewriting its ownership marker. It never changes
desktop display or theme settings. Every attempt has a fresh directory and a
receipt, including failed attempts.

Seven backend-shaped cases are adapted to the production GTK presentation
record. The 56 cells cover those cases at four requested scale settings in
Adwaita and HighContrast. The 200% case uses GDK_SCALE=2; 125% and 150% use
GDK_DPI_SCALE font scaling. Receipts verify the observed widget scale and Pango
font DPI, and explicitly identify these toolkit fixtures. They are not physical
monitor transitions. Native assertions cover page accelerators, forward Tab
focus entry, action focus/allocation within every ancestor, exact recordings,
unchanged state, empty/error absence, and appearance recovery. The external
AT-SPI probe requires a single exact window and PID; it checks labels, roles,
visibility and availability only within that window.

GTK currently presents instance summaries rather than the Windows instance
list. Its overflow case qualifies long Unicode text, native wrapping/ellipsis
and the full accessible identity. It does not claim 41-row GTK list coverage.
PNGs, observed body-text contrast, unknown-glyph counts, action receipts, fixture
bytes, source hashes and both executable hashes remain bound to each run.
Historical WSL and hosted receipts exposed missing Unicode glyphs. The native
gallery now counts unknown glyphs in mapped production labels on every visited
page, as well as the full instance identity. Each run hashes the host's font
files before and after its cells. `--require-fixture-glyph-coverage` refuses a
run with missing glyphs and retains all observations. CI provisions the Noto
core, CJK and emoji fonts and requires this check. Coverage applies to these
observed fixture layouts; it does not establish coverage for all Unicode text.

Neither gallery closes physical-monitor, human keyboard/screen-reader,
arbitrary host/font configurations or packaged-candidate obligations, or claims Beta
readiness. The WorkUnit stays active until its remaining qualification is
recorded against the actual candidate.

Packaged WinForms qualification must bind the managed assembly actually present
in the archive to the controls loaded by the test host. A separate successful
WinForms build is insufficient. External frontend composition uses the exact
bundle destination populated during staging; it cannot select the CLI through
a filename alias. The product layout uses root FacMan.exe, while the legacy
layout may use bin/FacMan.WinForms.exe. Missing staged frontends fail packaging.
A gallery host loading those exact package bytes still does not qualify the
ordinary product entrypoint, live backend, physical display or human experience.
