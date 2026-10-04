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

`profiles plan` and `profiles apply` report the source manifest revision and
the effective value of each supported setting. Their provenance identifies
which values came from the stored profile and which were supplied by the
current request. Extra arguments carry individual origins, including when a
request repeats an argument already present in the profile. The ordinary CLI
prints these values and origins; `--json` retains the typed response. The
stored profile is the base layer, so its own historical template-versus-edit
origins are not inferred from current values.

The returned `plan_sha256` binds the instance manifest, exact profile source,
existing override bytes or their absence, and the requested effective values.
Pass it as `--expected-plan` to apply that reviewed preparation. Changed inputs
refuse before a new transaction begins. `--expected-revision` retains its
instance-manifest-only meaning. Apply also rechecks its frozen input identity
before publication; a late change retains the journal and staging for explicit
recovery. These owner-level plans provide one subplan for Make Ready; they do
not grant launch or setup authority.

Safe fields cover window/fullscreen preference, graphics quality, audio,
instance-local save selection, headless or benchmark planning modes, bounded
benchmark ticks, and an explicit argument allowlist. FacMan always owns
`--config`, `--mod-directory`, the executable, working directory, and effective
write-data controls. Profiles cannot contain commands, scripts, executable
paths, setup mutations, network endpoints, credentials, or raw JSON fragments.

`profiles archive` moves unused workspace profiles to FacMan-owned trash. It
does not permanently delete profiles, and shipped profiles remain immutable.
