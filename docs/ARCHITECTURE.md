# Architecture

FLaunch is the Factorio-facing product binding and app shell for a future
universal launcher ecosystem.

```text
universal-setup
  owns install mutation, verification, repair, uninstall, audit

universal-launcher
  owns product registry, instances, profiles, launch plans, accounts, caches

factorio-launcher
  owns Factorio discovery, Factorio UX, Factorio mod/save/server workflows
```

The universal launcher should understand artifact sets, launch plans,
instances, profiles, and diagnostics. It should not understand Factorio mods.

