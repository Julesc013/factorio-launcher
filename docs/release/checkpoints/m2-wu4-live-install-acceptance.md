<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU4 Live Synthetic Install Acceptance

Status: accepted exact-`dev` integration proof and retained live lifecycle
machine proof recorded; human verdict `pending`.

This checkpoint binds the first authorized synthetic-product lifecycle below
`D:\FacMan-Live-Acceptance\M2`. It is not a human `Pass`, ordinary live apply
promotion, Factorio archive acceptance, recovery apply proof, or execution
authority.

## Provider identities

| Evidence | Identity |
| --- | --- |
| Universal Setup runner used live | `6209385f25db1824bcbb7ec599cf2152606be89b` |
| Universal Setup reviewed task head | `169d4da80b886ed96f1e5450ddc5a3be1a44c085` |
| Universal Setup canonical `main` | `9b8196437e41e45bd8d5a613246dabe5b8cdb968` |
| provider push CI | `29334554537` |
| provider PR CI | `29334556981` |
| provider exact-main CI | `29334632894` |
| FacMan consumer revision used live | `a8b298a35cd1587cea566886b5a3891153a2b7f2` |
| FacMan provider-pin commit | `2d8b723ef04868063f8668810b9be68e542f9f03` |

## FacMan integration identities

| Evidence | Identity |
| --- | --- |
| reviewed PR | `#18` |
| task head | `a286b5c42736e1a4189030a51e9b1e5c397552eb` |
| task tree | `8027f6fe9a54e1b845842934d21fa142895b50f9` |
| `dev` merge | `5563e3b8de4363d1d42cc2ba6f5829aed0c7405e` |
| `dev` tree | `8027f6fe9a54e1b845842934d21fa142895b50f9` |
| exact-`dev` CI | `29337542209` |
| exact-`dev` CodeQL | `29337541636` |
| exact-`dev` security policy | `29337541937` |

The task and merge trees are identical. All three exact-`dev` workflow runs
completed successfully; this accepts integration without changing the pending
human verdict or any setup/execution authority.

## Retained live run

| Evidence | Identity |
| --- | --- |
| run ID | `m2wu4-20260714-01` |
| summary SHA-256 | `0d42f22f40aa2b92df49b8bd872db9ad2367c5000d615a6d982f25e4ee0a0507` |
| synthetic ZIP SHA-256 | `02bed514abfac0145cb8e57008aeff3f2107715ea8a3f57ebed78ce456b2ddbf` |
| install packet | `b0142866654c5fcff24d4c04d8665cfc55f1e107f1cc4454f59e6e139913b225` |
| repair packet | `14eec52ae99058d93f1ad6f56ddb9cb97452503c64f92521de06a66349029ea6` |
| move packet | `7b01758b510e65a3007681c196cfd4703c1e83c6614f8edde806d9613673ef8d` |
| uninstall packet | `1f4960afad49f519f191b2d6d5e33fb3f13adb90b4bd65fe058a43b80b798b0b` |
| audit head | `8228808f068e7e929d7490ce05c1e2c56e3d4155cfdfad88cd354cc070db2dc1` |
| final installed state | `180c9962db0346442cfdb5a404765ac8d3c8d5a01f0d4c65ad1e3f497d2a7dd0` |
| final ownership | `ccd52536ea44b75f58e44b6c6035d7e213ad3724c30bd8f746c6f3a33d41ba5c` |

The archive contains three harmless text/data files and no executable code.
Install verification passed; deliberate owned-file damage was detected; exact
repair passed; same-volume move passed with the old root retained; foreign
content caused a no-mutation refusal and was retained; exact external removal
was recorded; clean uninstall removed the current owned root. The final state
is `retired` with recovery `not_required`.

Cross-volume move was not attempted because no second volume is authorized.
That is an explicit unproven lane, not a skipped success.

## Repository and package proof

- combined Release CTest passed 39/39;
- the complete Python suite passed 339 cases with one opt-in skip;
- strict and AIDE portable validation passed;
- required Windows package proof passed 14/14 with zero skips;
- reproducibility passed over a 388-file selected package tree.

| Reproducible evidence | SHA-256 |
| --- | --- |
| archive | `9a26fa612773108ae4e2f2f1762f9561df3f850459065abdfc2f9e608bc1ca55` |
| package tree | `4dcf73452223cede21d24a74b5637289dc8b1509e1e72957f8f7f13d61389195` |
| SBOM | `1589f6c625a3580fc5264e887f5260917bd428124573cac060c35aae1c975f82` |
| provenance | `a9be745af843b98b30cedd72f0359f131c98f87f1d5ddc190a19f717f30771c4` |

The package remains unsigned and unpublished; its reproducibility and
integrity do not prove publisher authenticity.

## Authority retained

- every evidence packet has a pending operator verdict;
- automation cannot record `Pass`, `Fail`, or `Inconclusive`;
- ordinary managed-portable apply remains unavailable pending a human verdict;
- `recovery.apply` remains unavailable pending WU5;
- existing Factorio installations and Steam were untouched;
- network, credentials, registry, shortcuts, elevation, package managers,
  installer/product execution, signing, publication, H1, and Safe beta remain
  unavailable.
