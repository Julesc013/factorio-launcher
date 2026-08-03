# FacMan Windows WinForms C1 shell

The C1 reference shell is a native Windows Forms product surface for Windows
10 and Windows 11 x64. It renders the already-frozen FacMan-local
`facman.presentation.v0` semantics; it does not extend that contract with
toolkit types and does not move any semantic record into Universal Launcher.

## Product structure

Four pages remain in the main navigation:

| Page | Player purpose |
| --- | --- |
| Instances | Select or create an isolated instance and understand its current readiness. |
| Installations | Inspect and rescan existing installations without implying repair or update ownership. |
| Activity | Observe backend-owned running, exited, interrupted, and recovery records. |
| Settings / About | Read product, appearance, platform, transport, evidence, and authority truth. |

The Launch Deck remains visible below every page. It shows the selected
instance, current readiness revision, primary and secondary actions, status,
exact refusal or recovery detail, and Last Run. The generated catalog is not a
top-level product journey; its existing forms and bounded process client open
only from Advanced.

## Deterministic state rendering

The executable embeds the five canonical fixture records and parses them with
a toolkit-neutral adapter:

- `positive` shows current readiness and fixture-only Play;
- `refused` keeps Play selectable only to expose the exact `stale_readiness`
  code, observed/current revisions, detail, and Rescan action while starting no
  process;
- `running` replaces Play with Show in Activity and displays the exact
  backend-owned operation;
- `exited` displays ordinary exit, Last Run, and fixture relaunch;
- `interrupted` retains the operation and recovery identities and exposes
  inspect before explicit recovery.

The Settings/About evidence chooser and Evidence menu select these immutable
records for review. They are prototype evidence controls, not production
commands. Fixture Play only transitions the in-memory presentation to the
canonical running record. Rescan and recovery return to the ready fixture and
never auto-launch. The complete embedded journey starts no Factorio process.

## Keyboard and accessibility

The shell uses Windows-native menu, tab, list, label, button, combo-box, group,
dialog, and status controls with system colors and the system message font.
Navigation has access keys and `Ctrl+1` through `Ctrl+5` shortcuts. Actions have
mnemonics, deterministic tab order through native container order, explicit
accessible names and descriptions, and a status announcement after state
changes. Enter invokes the current Launch Deck primary action; Escape retains
native dialog cancellation.

`AutoScaleMode.Dpi`, a 96-DPI logical design surface, Per-Monitor V2 manifest,
docked/percentage layouts, wrapping action rows, and a bounded logical minimum
size cover 100%, 150%, and 200% Windows scaling without custom pixel rendering.
System Native mode uses no custom theme, owner-drawn controls, fixed bitmap
text, or hard-coded foreground/background palette.

## Portable ZIP prototype

`tools/build_winforms_c1_portable.py` creates a deterministic unsigned archive
with the x64 shell, explicit authority notice, optional colocated FacMan CLI,
and a SHA-256-bound prototype manifest. The presentation fixtures are embedded
in the executable, so the four-page shell remains usable when relocated.

The archive is explicitly `fixture_only`, unsigned, unpublished, and not a
release artifact. When the optional CLI is absent, Advanced returns the
existing exact `frontend_backend_unavailable` refusal. When it is present,
Advanced keeps the existing bounded process RPC transport.

## Scope and evidence limits

This WorkUnit proves C1 reference-shell source, deterministic rendering,
Windows x64 compilation, accessibility/scaling construction, and portable ZIP
shape. It does not prove a live Factorio launch, route capability, performance
budget, visual screenshot matrix, screen-reader behavior on every Windows
build, signing, publication, or protected/writable-state observation. Those
claims still require their named live acceptance or release evidence.

No daemon, direct client, transport rewrite, route promotion, runtime
qualification identity, setup mutation, network behavior, custom theme,
AppKit/GTK support promotion, revalidation procedure, or Universal Launcher ABI
work is included.
