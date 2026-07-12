# Local mod inventory

`mods list`, `inspect`, `verify`, `index`, and `explain` provide a read-only
inventory of local Factorio mod archives. The inventory always covers the
non-recursive `mods/` root of every registered instance. `mods index` may add
explicit absolute roots with repeatable `--root` options; it never performs an
arbitrary recursive workspace scan.

Archive records include stable SHA-1 compatibility and SHA-256 identity,
archive and expanded sizes, production archive-policy status, required,
optional, hidden-optional, and incompatible dependencies, plus instance and
lock references. Reads use no-follow stable handles and revalidate identity.
The commands do not mutate source archives and do not access the Mod Portal.

Built-in packages are virtual dependency records derived from each registered
install's direct `data/*/info.json` metadata. This permits `base`, `quality`,
Space Age features, or future built-ins to reflect the actual install instead
of a universal hardcoded list.
