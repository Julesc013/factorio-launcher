# FacMan alpha.5 promotion and candidate closeout

Date: 2 September 2026

WorkUnit: `FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01`

Candidate producer: `FACMAN-0.1-BETA-READINESS-01`

State: `exact_candidate_passed_source_bound_non_authorizing`

## Disposition

The hosted product-candidate workflow passed for the exact pre-closeout source
revision `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` and tree
`1ebcd2b230ed188e021880ffa4c438de2ede655b`. It produced and independently
verified the exact unsigned, unpublished six-product candidate closure. This
is machine evidence for that source only; it is not a beta verdict, tag,
release, signing, notarization, publication, support, or human acceptance.

The protected topology is deliberately recorded as three distinct revisions:

| Boundary | Revision |
| --- | --- |
| repaired `dev` promoted by PR #237 (`D`) | `d5bd6a18abd21d48359a05be6c3798fa224e95e3` |
| canonical `main`, candidate source (`M`) | `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` |
| ancestry synchronization on `dev` by PR #238 (`S`) | `43af71f8231c5a1b843636df7fd0ab8a6040d25c` |
| common source tree (`T`) | `1ebcd2b230ed188e021880ffa4c438de2ede655b` |

Tree equality does not transfer revision qualification. Neither this closeout
revision, `S`, nor any later `main` revision is qualified by the run against
`M`; every future revision requires a new candidate run.

## Failure and repair chronology

1. The first dispatch request received HTTP 422 before GitHub created a run.
   Its run ID and attempt are therefore `0`; the request timestamp and response
   body were not recorded and remain `UNRECORDED`. The evidence source is the
   body of pull request #230. Repairs were
   `c18d6743c306b884615b7134504a00f7716b818f` and
   `d38dbc30650c8cdb9d40f711c6677734d5247c2b`.
2. Run `33557664813`, attempt 1, failed the contract job at repository module
   import. Repair `10da832ef7777f6224de54fb01c972991aae297c`
   produced the successor candidate source.
3. Run `33567017006`, attempt 1, exposed a checkout-owned Windows credential
   include and a macOS runner temporary root resolved through a symlink. Its
   one Linux artifact was `9823610585`, digest
   `sha256:e46a2e644613d376f59cbef1491407bb72709790df8f90e661c3e3158b6693ea`.
   Repair `f43049d4db4b20c14f0a637bf426f95873ba7892` entered repaired `dev` as `D`.
4. Run `33576140943`, attempt 1, was dispatched exactly once at `M`, with no
   overlapping active run, and completed successfully.

No failure was rerun in place and no missing timestamp or response body has
been reconstructed.

## Passing workflow proof

Workflow ID `347619223`, path `.github/workflows/product-candidate.yml`, used
the file at blob `35c98c40fd8710d567ecd2157584c9ea5c56dfa2` with raw SHA-256
`11f56d06b3154c883beee20d278ae4a36690680c7718136478f815c416ebb00d`.
The event was `workflow_dispatch`, ref and head branch were `main`, and the
head SHA was exactly `M`.

| Job ID | Exact name | Result |
| ---: | --- | --- |
| `100080412106` | Version-current candidate contract | success |
| `100080456660` | Linux x64 unsigned preview candidate | success |
| `100080456693` | macOS Intel unsigned preview candidate | success |
| `100080456726` | Windows x64 unsigned candidate | success |
| `100081901409` | Exact six-asset unpublished candidate bundle | success |

Exactly four workflow artifacts were recorded:

| Role | Artifact ID | Digest |
| --- | ---: | --- |
| final bundle | `9826850751` | `sha256:2afe4529f056ac4400352400418e5cede776146e9ef803aa4901cc76944f71c5` |
| Windows input | `9826842304` | `sha256:a2b58ef796dfc7daf35d0993e02bdf5807937cf1c3dea5ae035fd4d45b510f82` |
| macOS input | `9826791575` | `sha256:530533736e47233f0f005a27b576760261bef44a7b3ace19c386047a7804bf8b` |
| Linux input | `9826768803` | `sha256:6c8f0854d863de5bea7d9b5d97ad74be3c8720020c815b531b43835987065e0d` |

The receipt preserves every artifact name, byte count, node ID, API/download
URL, creation/update/expiry time, expiry observation, workflow binding, and
full digest.

## Independently verified bundle

Only final artifact `9826850751` was downloaded. It was verified outside the
repository in the marker-owned task root identified by the portable locator:

```text
facman-development://tasks/FACMAN-0.1-BETA-CANDIDATE-33576140943-20260902T0046Z/bundle
```

The locator binds the marker task identity without embedding an ephemeral
operator profile or machine-specific development root in product metadata.

`tools/product_candidate.py` passed the exact flat 14-file closure: six
products, six evidence files, `SHA256SUMS`, and
`product-candidate-bundle.v1.json`, totalling 47,353,341 bytes. The receipt
records each filename, byte count, and SHA-256. It cross-binds the manifest to
repository, workflow, run, attempt, source revision/tree, product version,
candidate class, the three payload-equivalence adapters, and its all-false
authority map. Windows, macOS, and Linux payload equivalence passed against
their canonical platform stages; that proof grants no release qualification.

## Provider and archive bindings

The candidate retains the exact Universal Launcher and Universal Setup pins
and digests. The provider-lock SHA-256 is
`d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00`;
the workspace-lock SHA-256 is
`b1590cc87bd50e5913196f1e3aa7a044028b30e9f1354b46a355b3db3f42c9bf`.

The completed foundation tasks are immutably archived at checkpoint
`facman-0-1-alpha5-foundation-closed-2026-09-02`. Its history index SHA-256 is
`eecc84950b0905e14f22ea5ad35066ec39cbd8fabf1d75ccb5a8b62164435c73`
and binds exactly two task records.

## Remaining human and external gates

The exact candidate is passed, but beta readiness remains false. Human GUI and
accessibility testing, Factorio execution, live managed-install acceptance,
performance/security/fault campaigns, signing, notarization, tag allocation,
publication, support, and route promotion remain separate gates. Qt6, WinUI,
and SwiftUI remain deferred lanes. The receipt intentionally keeps every
tag/release/beta/signing/notarization/publication/support/human/Factorio/route/
live-install authority field false.

The machine-readable authority for this checkpoint is
`release/index/alpha5_promotion_candidate_closeout.v1.toml`; the checker is
`tools/alpha5_promotion_candidate_closeout_check.py`.
