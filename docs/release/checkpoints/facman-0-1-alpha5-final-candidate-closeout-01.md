# FacMan Alpha.5 final-candidate closeout

Date: 2 September 2026

WorkUnit: `FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01`

State: `final_candidate_machine_qualified_truth_closed`

## Disposition

FacMan's current Alpha.5 candidate is the exact unsigned, unpublished output
of product-candidate run `33603385303`, attempt 1, at canonical `main`
revision `4683ecd9a1b9ead5eb84be152760d12583da0f0e`. Protected `dev` is
`488994a81ddb5eb54d541ef3a48b64ca83f67d4a`; `main` is its ancestor and both
revisions resolve to tree `c07938618bc0f533fd12756cba123f54b8592048`.

This establishes engineering completion and machine qualification for those
exact candidate bytes. It does not establish beta allocation, human desktop
acceptance, real Factorio Play, managed-install acceptance, cross-platform
human acceptance, signing, notarization, tagging, publication, or support.
Tree equality does not let the truth-only `dev` synchronization or any future
product revision inherit the candidate run.

## Hosted candidate proof

The `.github/workflows/product-candidate.yml` run completed successfully with
five successful jobs: version-current contract, Windows x64, macOS Intel x64,
Linux x64, and exact six-asset bundle assembly. GitHub retained exactly four
workflow artifacts.

| Role | Artifact ID | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| final bundle | `9836639957` | `39,415,203` | `1c53c1e1337dced910f8aa88c9d32c9a36a68d5b87dff2cce7172381f386e736` |
| Windows input | `9836247157` | `16,038,042` | `88917bebd2861d33f7a893c266d7b03decb11cf65ddfb0642289ce788d758981` |
| macOS input | `9836629744` | `13,398,912` | `9c87920676ba1a974e877915cec2423ea2b6228fe399b26e3ad17ee35788294d` |
| Linux input | `9836125335` | `9,976,347` | `64be7ee79a234924cbf0a80f7bb2e463f049da6a2f7abf58d1341b0e63508bb6` |

The final artifact name is
`FacMan-0.1.0-alpha.5-unsigned-unpublished-candidate-33603385303-1-4683ecd9a1b9ead5eb84be152760d12583da0f0e`.

## Durable exact-byte custody

The extracted 14-file bundle is retained under the no-clobber locator
`facman-custody://candidates/facman-0.1-beta-candidate-main-4683ecd9-run-33603385303`.
It contains six product packages, six platform evidence files, the bundle
manifest, and `SHA256SUMS`, totalling 47,428,808 bytes. The manifest SHA-256 is
`1be3a4ade7370a6c0ed51dc04eff5ce2ad86eb8034393cdaefa961acd8d4a923`;
the checksum-file SHA-256 is
`a9b8d06fc6d5062b41e68215399680dfa66689e3dacf9d062424f5d1547944b7`.
The repository checker can validate an operator-supplied custody root without
embedding its machine-specific path in release truth.

Payload-equivalence closure passed for the Windows setup overlay, macOS pkg
root, and Linux embedded archive. Runtime resources are also bound exactly:
600 entries, 2,233,690 expanded bytes, content SHA-256
`4c9802f155c24f289c4d005d06b55bf1769cd939dbce62321875d5a21817827d`,
and pack SHA-256
`ce95c45eb588fae9c0baee6199624e64d90cb872e71b6ba9945126c86c9dc10b`.

## Provider and history boundary

The provider lock SHA-256 remains
`d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00`;
the workspace lock SHA-256 remains
`b1590cc87bd50e5913196f1e3aa7a044028b30e9f1354b46a355b3db3f42c9bf`.
Universal Launcher is pinned at `5479939ca5cbc9ee0f901608a92012778b4752ae`
and Universal Setup at `d2a2aae7e61c47035c92334b0522143b4fea3880`.

The earlier Alpha.5 promotion-candidate receipt and the exact Alpha.3 draft
distribution remain immutable historical evidence. Neither is a current
candidate or current distribution. The current machine-readable authority is
`release/index/alpha5_final_candidate_closeout.v1.toml`, validated by
`tools/alpha5_final_candidate_closeout_check.py` and the release-identity,
programme, readiness, package, schema, project-state, and AIDE truth checks.

## Remaining gates

Before a truthful beta can exist, the repository still needs the planned
current-view and release-governance consolidation, Alpha.6 workspace migration
and managed-install lifecycle, Alpha.7 content/world and Play/frontend
convergence, feature-freeze qualification, a fresh exact beta candidate, and
human verdicts bound to those final bytes. Release tags remain immutable and
all signing, notarization, publication, support, protected-setting, execution,
and live-install authority remains outside this checkpoint.
