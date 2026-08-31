# Validation

- PR #218 merged to `dev` as `e1429dd15d59bac1d1cf736d82d219dde752fe21` after 26 successful checks.
- PR #219 merged to `main` as `227257f36b1d37d5ca13ad3b49cbd7d90836790c` after 51 successful checks and two intentional non-tag skips.
- `main` and `dev` source trees are identical at `1b13eb46dda48672bafda5e458494e2084297251`.
- Canonical `main` workflows `33386152464`, `33386152518`, `33386152497`, `33386152557`, `33386152469`, `33386152527`, `33386152530`, and `33386152645` passed.
- Annotated tag object `7aec84204521685568d98d5136ebfd529f08a664` peels to canonical commit `227257f36b1d37d5ca13ad3b49cbd7d90836790c`.
- Tag run `33391586142` passed all three product jobs, the distribution contract, and exact six-input gate. Its final release job exposed two deterministic release-only defects, which were recovered without moving the tag and are fixed by `FACMAN-ALPHA3-RELEASE-RECOVERY-01`.
- The draft contains exactly eight assets. Download-back verification matched every SHA-256 and the evidence archive binds the canonical commit, tree, and tag object.
