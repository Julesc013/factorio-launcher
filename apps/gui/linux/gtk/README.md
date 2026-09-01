# Linux GTK 3/X11 C1 preview

This is the native GTK 3 projection of backend-derived FacMan C1 state over the
existing bounded process RPC for the frozen Linux x64/X11 preview lane.
Deterministic fixtures remain only behind explicit
`FACMAN_PRESENTATION_MODE=evidence`. It is not a live Play,
runtime-qualification, package-publication, or stable-support claim.

The shell uses native GTK 3 widgets for Instances, Installations, Activity,
Settings/About, Advanced, and a persistent selected-instance Launch Deck. The
menu bar, mnemonics, Control-1 through Control-5, native focus behavior, and
ATK names/descriptions preserve GTK keyboard and accessibility conventions.
System Native is the safe default. FacMan OEM+ applies only a semantic Launch
Deck class and Control-0 restores System Native.

Explicit evidence controls cover selection/create, readiness, exact `stale_readiness`
refusal before effects, backend-owned running/exited state, Last Run, relaunch
with a distinct operation ID, and interruption/recovery. They start no Factorio
process. Advanced commands use a fixed `rpc --stdio` child process. Stdout and
stderr are drained incrementally, and the client terminates the process group
as soon as either fixed byte ceiling is exhausted. A 30-second deadline,
strict UTF-8 and JSON parsing, duplicate-member rejection, bounded nesting, and
exact request/command/operation/attempt correlation protect the response seam.
Every post-dispatch transport ambiguity is reported as `outcome_unknown`.

The public application and icon identity is `io.github.julesc013.facman`.
Product, semantic version, desktop entry, and Meson project version are
generated from `release/index/version.v2.toml`; experimental is a support tier,
not part of the public identifier.

Build and stage the package prototype on the frozen GTK 3/X11 environment:

```sh
FACMAN_GTK_BUILD_ROOT=/absolute/external/facman-gtk-build
FACMAN_GTK_STAGE_ROOT=/absolute/external/facman-gtk-stage
meson setup "$FACMAN_GTK_BUILD_ROOT" apps/gui/linux/gtk --prefix=/usr
meson compile -C "$FACMAN_GTK_BUILD_ROOT"
DESTDIR="$FACMAN_GTK_STAGE_ROOT" meson install -C "$FACMAN_GTK_BUILD_ROOT"
```

The staged public executable is `usr/bin/FacMan` and the desktop entry is
installed below `usr/share/applications`. This shell adds no daemon, direct
client, runtime route, transport rewrite, or Universal Launcher ABI.
