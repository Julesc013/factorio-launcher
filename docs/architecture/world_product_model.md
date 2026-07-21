# World product model (superseded)

The earlier target architecture treated `World` as FacMan's primary product
aggregate. That decision is superseded by the
[`Instance product model`](instance_product_model.md).

The correction preserves saves/worlds as important portable content, but an
instance is the runnable aggregate. A player selects an instance and launches
to Factorio's main menu with its version, mods, profile, account context,
settings, saves, and resources in effect. Selecting or creating a save inside
Factorio does not redefine the instance.

Future save/world portability belongs to the secondary
`FACMAN-WORLD-BUNDLE-AND-SAVE-COMPATIBILITY-01` lane. It owns portable
version/modset/content requirements, compatibility analysis, import/export,
and creating or preparing an instance from a world bundle; it does not restore
World as the launch aggregate.

Historical checkpoints and reviews may still refer to WorldSpec/WorldBinding;
those records describe the accepted direction at their recorded revision and
must not be rewritten. New product work uses InstanceSpec, InstanceBinding,
InstanceReadiness, InstanceView, and explicit launch intents.
