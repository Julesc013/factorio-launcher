# Launch Profiles

Launch profiles turn user intent into structured Factorio command-line flags.

Initial profiles:

- gui (normal menu)
- load-save
- multiplayer-connect
- host-game
- headless-server
- benchmark
- map-preview
- mod-dev
- safe-graphics
- low-vram

This document describes the implemented `LaunchProfile` facet. The target
instance model adds separate Graphics, Audio, Interface, Multiplayer, Server,
NewGame, and Backup profile families rather than flattening every setting into
one launch profile. A future `LaunchIntent` selects the run action; `menu` is
the default and does not add a save, server, benchmark, or editor target.

Every profile supports a dry-run launch plan. R3.7 stores workspace profiles as
portable `factorio.launch_profile.v1` documents and layers them over the
immutable shipped `vanilla` template, the instance profile selection, and
typed instance-safe overrides. `profiles apply` always materializes the same
effective-profile plan first, backs up the instance manifest, and keeps
`run.execute` quarantined.

Safe fields cover window/fullscreen preference, graphics quality, audio,
instance-local save selection, headless or benchmark planning modes, bounded
benchmark ticks, and an explicit argument allowlist. FacMan always owns
`--config`, `--mod-directory`, the executable, working directory, and effective
write-data controls. Profiles cannot contain commands, scripts, executable
paths, setup mutations, network endpoints, credentials, or raw JSON fragments.

`profiles archive` moves unused workspace profiles to FacMan-owned trash. It
does not permanently delete profiles, and shipped profiles remain immutable.
