# Release

Owns package manifests and release profile definitions.

May contain:

- platform package manifests
- package layout declarations
- release/build profile descriptions

Must not contain:

- compiled output
- source implementation
- user state
- downloaded Factorio binaries

Generated artifacts belong in ignored roots such as `build/`, `dist/`, or
`out/`.
