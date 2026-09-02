# Validation

Result: PASS for the local promotion obligation profile and for the exact
non-publishing hosted product candidate. Release and human authority remain
separate and ungranted.

Command:

```text
py -3 tools/dev.py test release --full --obligation-profile promotion
```

Recorded results:

- Native test suite: 41/41 passed.
- WinForms build: .NET Framework 4.8 completed with 0 warnings and 0 errors.
- Python test suite: 1,417 tests run with 0 failures, 0 errors, and 9
  classified skips.
- Python skip accounting:
  - optional: 2;
  - unsupported: 5;
  - not applicable: 2;
  - required blocked: 0; and
  - unknown: 0.
- Strict validation passed with 399 schemas, 127 commands, 247 refusal codes,
  and 128 goldens.
- The post-commit GTK remediation suite passed 33 focused package-proof,
  classic-shell, generated-metadata, and live-shell tests. The strict gate also
  passed after the repair, including source-size and manual-JSON budgets.

Hosted feedback:

- PR 227 run `33523786560` built and tested the Linux native and GTK targets,
  then failed the external AT-SPI lookup because the probe retained the old
  `FacMan GTK 3 C1 Preview` title while the binary used generated alpha.5
  product metadata.
- The repair now passes the generated title into the external probe and emits
  a schema-valid, request-correlated `facman.transport_response.v2` fixture.
- PR 227 merge ref `a5cc990d0a684a24f681eed9a0f10a2e09071d54`,
  associated with repair head `f6546d2d24bce1fa198f7e923d0a6a73e9384356`,
  has the identical tree `b6cf55caffdeeeacd3a1856e30143dba727c0d4b`
  and passed `linux-native` job `99929032838` in run `33529589182`, including
  the generated-title GTK build, package, runtime, and external AT-SPI proof.

Product-candidate chronology:

1. The first manual dispatch attempt was rejected by GitHub with HTTP 422 and
   created no workflow run. No trustworthy timestamp or response body was
   retained, so neither is reconstructed here. Repair `c18d6743` moved
   runner-dependent root binding after runner allocation; `d38dbc30`
   synchronized that repair with `dev`.
2. Run `33557664813`, attempt 1, at source
   `67e25b38130a2f939bdbf67a2623bb71a41ab0bd` was created at
   `2026-09-01T20:50:29Z` and failed during the contract job because a Python
   entrypoint could not import the repository module. Repair `10da832e` made
   the candidate Python entrypoints import-safe.
3. Run `33567017006`, attempt 1, at source
   `680c22aa0a457668475d8087ee28b9cb6e0791d6` was created at
   `2026-09-01T22:35:08Z`. Windows failed on the checkout-owned include seen by
   source observation, and macOS failed because its temporary root resolved
   through a symlink. Linux passed far enough to upload artifact `9823610585`,
   digest
   `sha256:e46a2e644613d376f59cbef1491407bb72709790df8f90e661c3e3158b6693ea`.
   Repair `f43049d4` added the bounded Windows checkout-include scrub and the
   no-link macOS temporary-root preparation.
4. Final run `33576140943`, run 9, attempt 1, was dispatched once against
   `main` at exact source
   `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` and tree
   `1ebcd2b230ed188e021880ffa4c438de2ede655b`. It ran from
   `2026-09-02T00:38:12Z` through `2026-09-02T00:45:42Z` and completed with
   conclusion `success`.

The final run contained exactly five successful jobs:

- `100080412106` - Version-current candidate contract;
- `100080456660` - Linux x64 unsigned preview candidate;
- `100080456693` - macOS Intel unsigned preview candidate;
- `100080456726` - Windows x64 unsigned candidate; and
- `100081901409` - Exact six-asset unpublished candidate bundle.

It produced exactly four unexpired workflow artifacts:

- final bundle `9826850751`, digest
  `sha256:2afe4529f056ac4400352400418e5cede776146e9ef803aa4901cc76944f71c5`;
- Windows input `9826842304`, digest
  `sha256:a2b58ef796dfc7daf35d0993e02bdf5807937cf1c3dea5ae035fd4d45b510f82`;
- macOS input `9826791575`, digest
  `sha256:530533736e47233f0f005a27b576760261bef44a7b3ace19c386047a7804bf8b`;
  and
- Linux input `9826768803`, digest
  `sha256:6c8f0854d863de5bea7d9b5d97ad74be3c8720020c815b531b43835987065e0d`.

Only the final artifact was downloaded, into the marker-owned external root
`C:\Users\Jules\AppData\Local\FacMan\Development\repositories\factorio-launcher-5db2844e2f29\tasks\facman-0.1-beta-candidate-33576140943-20260902t0046z\bundle`.
`py -3 tools/product_candidate.py verify --root <that-root>` passed with
exactly 14 flat files. The manifest binds version `0.1.0-alpha.5`, the exact
source and tree above, repository/workflow/run/attempt, six products, six
evidence records, `SHA256SUMS`, and the three payload-equivalence adapters.
Its authority ceiling remains explicitly false for tag, release, publication,
signing, and support.

Together, the local command, hosted GTK repair proof, and final candidate run
establish machine qualification for this source. They do not supply human GUI
or accessibility verdicts, accepted Play/install journeys, signing or
notarization, a release tag, publication authority, or support approval.
