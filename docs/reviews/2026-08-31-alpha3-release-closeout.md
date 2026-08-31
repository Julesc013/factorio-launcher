# FacMan 0.1.0-alpha.3 release closeout

As of 31 August 2026, the owner-only alpha.3 draft exists with exactly eight
assets and has passed download-back SHA-256 verification. It remains a draft,
prerelease, unpublished, unsigned, unsupported manual-test candidate.

## Immutable identity

- Tag: `v0.1.0-alpha.3`
- Annotated tag object: `7aec84204521685568d98d5136ebfd529f08a664`
- Canonical source: `227257f36b1d37d5ca13ad3b49cbd7d90836790c`
- Canonical source tree: `1b13eb46dda48672bafda5e458494e2084297251`
- Dev integration merge: `e1429dd15d59bac1d1cf736d82d219dde752fe21`
- Draft release ID: `379745411`
- Draft release: <https://github.com/Julesc013/factorio-launcher/releases/tag/untagged-9a21056a92fbe6b680d5>

`main` and `dev` intentionally have different merge commit IDs and the same
source tree. The tag must not move. Any product-byte change requires a new
forward-only prerelease version.

## Asset result

The draft contains one portable and one setup product for Windows x64, macOS
Intel x64, and Linux x64, plus one checksum file and one evidence ZIP. There
are no separate CLI, TUI, WinForms, AppKit, or GTK downloads and no loose JSON
evidence sidecars.

The authoritative names, sizes, and SHA-256 values are recorded in
`release/ledger/0.1.0-alpha.3/draft-closeout.v1.toml`. All eight downloaded
assets matched the uploaded bytes, and the evidence ZIP binds the same source
commit, tree, and annotated tag object.

## Release-job recovery

Tag run `33391586142` passed all Windows, macOS, and Linux product jobs, the
distribution contract, and the exact six-input gate. Its final job stopped
before assembly or upload because checkout cleanliness was tested after the
job had downloaded untracked inputs. Manual recovery then exposed a second
release-only defect: the assembler read `known_limitations` from the TOML root
instead of `[inventory]`.

The draft was recovered from the same run's qualified products without moving
the tag. `FACMAN-ALPHA3-RELEASE-RECOVERY-01` moves the cleanliness check before
download, fixes the schema lookup, and adds regression tests. The failed final
job remains an honest historical record; product qualification did not fail.

## What happens next

Jules manually tests exact downloaded hashes on the intended machines and
returns results and notes. Record the asset filename, SHA-256, OS identity,
portable/setup mode, frontend route, and Pass/Fail/Inconclusive result.

Do not publish the draft, retag alpha.3, infer Factorio execution authority, or
allocate beta.1 until the human observations are triaged. Confirmed byte fixes
belong in a new forward-only prerelease.
