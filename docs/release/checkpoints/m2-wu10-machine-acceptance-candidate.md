# M2-WU10 Machine-Acceptance Candidate

Status: `EvidencePass`; local validation passed; hosted validation and
`MachinePass` pending.

## Accepted Identities

The journal-format correction merged independently in PR #27. The accepted
policy/verifier revision for this result lane is:

```text
26eb7056984b42859e377c1ffd0ffb7c80488078
```

The Universal Setup runner remains pinned to:

```text
3f8489275077347c2918f3bb03614ec6431362ff
```

The first `20260717-01` attempt remains blocked diagnostic evidence. It is not
reused as acceptance. The corrected result lane created two different fresh
children under the authorized root:

```text
m2wu10-20260717-02
m2wu10-20260717-02-interruptions
```

## Independent Observation

The verifier bytes were self-checked against the accepted revision before they
read the retained evidence. It derived `EvidencePass` with:

| Identity | Value |
| --- | --- |
| Lifecycle summary SHA-256 | `58c6d6568c3434c872d8efb9a39c3da20979bd8aa407cfb3d23b11a231e5fc74` |
| Interruption summary SHA-256 | `bb3f4d0827f3550da6ad0d50af7b5565c60e07f1350453986de30ec83b9a6785` |
| Synthetic archive SHA-256 | `02bed514abfac0145cb8e57008aeff3f2107715ea8a3f57ebed78ce456b2ddbf` |
| Evidence digest | `4de3e83c0abbe8b63f76cc6e31ece8ba2b6c052ab4cd1a94f56c76479ae502d2` |
| Observation SHA-256 | `fb0fcb58eec795d45a56cb48773d74ed74a38d4b14834a4921c1542310777181` |
| Verified at | `2026-07-17T06:25:00Z` |

The tracked observation is
`docs/quality/evidence/m2/m2-wu10-machine-acceptance.observation.v1.json`.
It binds 26 files, 14 directories, 40,105 bytes, zero reparse points, the four
packet file and payload digests, the five-event audit head, exact harmless
product bytes, clean final state, and the fresh 11-case/14-journal interruption
corpus.

## Candidate, Not Verdict

`EvidencePass` is the accepted verifier's filesystem observation. It is not the
technical acceptance verdict. The complete local matrix passed: 19 focused
tests, 234-schema strict validation, AIDE Lite, 41 native tests, 349 Python
tests with one expected opt-in skip, 14 clean-checkout package-runtime tests
with zero skips, and the clean three-repository reconstruction. This candidate
revision must still pass both push and pull-request hosted workflow sets.

After candidate CI passes, a later result commit may bind the candidate
revision, observation digest, local commands, PR number, and workflow run IDs.
That later commit must itself pass exact-head CI before merge. Only that record
may say `MachinePass`.

No human `Pass` is claimed. Human review is not required for this bounded
synthetic non-executable lane.

## Authority Boundary

The observation repeats the policy's authority *if* a final `MachinePass` is
recorded. This candidate does not promote it. Ordinary local managed setup
remains unavailable, and real Factorio archives, existing installations,
Steam, execution, H1, network, credentials, registry, shortcuts, elevation,
signing, and publication remain excluded.
