# Packaged Windows startup source checkpoint

The reviewed source fixes packed-schema verification, uses the supported launch
path from the retained backend handle, and rejects stale compiled identity.
Visual Studio builds through the shared helper require a clean rebuild with
dependency tracking disabled.

The original 8dc startup and stale-build failures remain in startup-custody.zip.
The archive also contains both exact source packets, the independent original
and final reviews, their compact reference closure, and helper admission logs.
startup-custody.json maps every archive member to its original bytes and binds
all 27 authored source paths. No original failure was overwritten.

The local p5d prototype passed the 44 native tests, focused Python and strict
checks, actual product and legacy identity harnesses, and ordinary GUI startup.
Independent review found no unresolved source issue. The changed-header
regression reproduced stale incremental output and current clean-build output.

These are source and prototype results. Build the committed successor from
empty owned native and GUI directories, compare the actual executed backend
identity with its package, and run packaged/installed checks before treating it
as a candidate. Hosted platform, real game, human and release gates remain open.
No tag, published release, provider adoption or beta readiness is asserted.
