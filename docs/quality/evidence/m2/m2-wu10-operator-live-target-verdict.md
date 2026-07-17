<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU10 Operator Live-Target Verdict

Status: machine evidence ready; human verdict `pending`.

This is the immutable historical preparation record merged by PR #25. The
later automated-acceptance policy does not rewrite this record or treat this
run as its sole passing result. A separate fresh run and result record are
required before `MachinePass` can be recorded.

Universal Setup completed the harmless synthetic lifecycle in the exclusively
created root below. Automation found no lifecycle failure, but that finding is
not a human `Pass` and does not enable ordinary live apply.

## Review identity

| Evidence | Identity |
| --- | --- |
| acceptance root | `D:\FacMan-Live-Acceptance\M2` |
| run | `m2wu10-20260715-01` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |
| FacMan baseline | `384c2569c84696c5fce02802684e30fad44f9ee0` |
| summary | `acceptance-summary.json` |
| summary SHA-256 | `3a0b7e080e83bd3bcb72c3e2198de1dc040e20e46d0e33ea1df11bd7967bec25` |
| archive SHA-256 | `02bed514abfac0145cb8e57008aeff3f2107715ea8a3f57ebed78ce456b2ddbf` |
| retained tree | 26 files, 14 directories, 40,105 bytes, zero reparse points |

The archive contains three text/data files and no executable code. The run
created no network, registry, elevation, package-manager, shortcut, Steam,
Factorio, credential, signing, publication, or process-execution behavior.

## What the run demonstrated

1. Install planning exposed and bound the archive, recipe, target, filesystem,
   three files, 95 bytes, and persistent effects.
2. Apply and verification passed without clobbering an existing target.
3. Deliberate owned-file damage produced the expected verification failure.
4. Repair restored the exact owned closure.
5. Same-volume move verified the new root and retained the old root.
6. Cross-volume move was not attempted because no second volume was authorized.
7. A foreign file caused uninstall refusal and was retained.
8. After exact removal of that test file outside Setup ownership, clean
   uninstall removed the current root.
9. Four operation packets, five audit events, installed-state, ownership, and
   journals remain for review; recovery is `not_required`.

The accepted WU5 interruption proof remains part of this review: 11 cases
produced one unchanged state, four reviewed rollbacks, three completed states,
and three visible `recovery_required` states. Its summary SHA-256 is
`c64ddfaa38bde351002d2840999b3ba74173cde8c76d3e6aa21891b5d169f6c1`.

## Operator review

Open
`D:\FacMan-Live-Acceptance\M2\m2wu10-20260715-01\acceptance-summary.json`,
inspect the retained `installed-product` text files and the four JSON packets
under `setup-state\evidence\packets`, and confirm that `moved-product` is absent.

Then report exactly one verdict with a short reason:

- `Pass`: the bounded synthetic portable lifecycle is acceptable;
- `Fail`: a concrete behavior is unacceptable;
- `Inconclusive`: the evidence is insufficient to decide.

A `Pass` can promote only local managed portable setup, verified Launcher
handoff, and FacMan synthetic/local managed setup candidacy. It cannot accept a
real Factorio archive, mutate an existing Factorio or Steam installation,
authorize `run.execute`, establish H1, or enable networking, credentials,
registry, elevation, signing, or publication.
