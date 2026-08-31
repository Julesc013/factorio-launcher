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
process. Advanced `product.inspect` uses a fixed `rpc --stdio` child process
with a 30-second deadline, bounded stdout/stderr, structured refusal, and
honest `outcome_unknown` on post-dispatch timeout.

Build and stage the package prototype on the frozen GTK 3/X11 environment:

```sh
meson setup build/gtk-preview apps/gui/linux/gtk --prefix=/usr
meson compile -C build/gtk-preview
DESTDIR="$PWD/build/gtk-stage" meson install -C build/gtk-preview
```

The staged public executable is `usr/bin/FacMan` and the desktop entry is
installed below `usr/share/applications`. This shell adds no daemon, direct
client, runtime route, transport rewrite, or Universal Launcher ABI.
