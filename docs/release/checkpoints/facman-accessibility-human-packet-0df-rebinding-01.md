# FacMan accessibility human-packet 0df rebinding 01

Date: 24 August 2026

State: `exact_candidate_bound_pending_human_execution`

## Outcome

The non-authorizing WinForms/TUI accessibility packet is now bound to the
already frozen product candidate qualified at source `0df94467`. This is an
evidence/configuration update based on evidence head `91a509bf`; it is not a
new candidate source, product build, release, or human verdict.

The source-owned validator accepts the bound pending packet only with the exact
qualified ZIP and resolution set. It checks package bytes and embedded stage
identity plus the resolution-set file, root, resolved-composition digest,
source tree, provider commits, and provider lock. Separate negative controls
refuse stale source, package, resolution file, resolution root, and provider
bindings. Completed-receipt mode also refuses the pending packet until the
human tester supplies a new receipt identity, tester, time, environment,
assistive technology, and direct observations.

## Exact binding

| Identity | Exact value |
| --- | --- |
| Evidence branch base | `91a509bf15410344527f1a8689d72a3198d7f29e` |
| Frozen candidate source/tree | `0df94467637836a364f684a43b887d8133ed4388` / `6c8cf9751f8be7f6ed2d2808dddc649b50d7c642` |
| Candidate identity | `facman-candidate-0df94467-cd79c8a9` |
| Canonical ZIP SHA-256 | `4d878d3dc2c1420360301b4af95669fc2fbf90cb569fe60febc8edc88a5fc870` |
| Resolution-set SHA-256 | `9514880baa0e4015362fbae45238484406998f32a192f8740a960b0fa5cb54d8` |
| Resolution root | `cd79c8a9be51ee1ecaf03cb5493814bd2226d19ad4016778896204cb4721b376` |
| Resolution digest | `996f1b3d80f27d140d229261c14df35308ee2b75d0d83b44f64ea8f8eaad004f` |
| Stage digest | `e805ed87df1264ba75cbfb45f374d0d519961dc5fd4ef29646f036cd28eb94bd` |
| Universal Launcher | `5479939ca5cbc9ee0f901608a92012778b4752ae` |
| Universal Setup | `d2a2aae7e61c47035c92334b0522143b4fea3880` |
| Provider-lock SHA-256 | `d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00` |

## Human boundary

All 12 required journeys and the overall result remain `Inconclusive`. Every
authority field remains false. The tracked packet contains no tester,
environment, assistive-technology observation, direct journey observation, or
accepted human judgment. It therefore closes the packet-executability gap only;
it does not close `accessibility.winforms` or `accessibility.tui`.

No Factorio process was run. Tagging, signing, publication, support promotion,
route promotion, beta/stable promotion, and acceptance of any human verdict
remain outside this checkpoint.

Work-Item: `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01`
