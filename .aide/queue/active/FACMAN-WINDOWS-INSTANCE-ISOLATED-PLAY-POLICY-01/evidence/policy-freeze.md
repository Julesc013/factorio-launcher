# Policy implementation freeze

The policy implementation freezes:

```text
policy_id       facman.windows-instance-isolated-play.2.0.77.x64.v1
policy_revision 1
claim_id        factorio.windows_instance_isolated_process_tree.v1
policy_digest   8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
```

The exact candidate remains Windows x64 Factorio 2.0.77 standalone,
non-Steam, `menu`, and `instance_isolated`.

## Frozen decisions

- One exact stable FacMan-owned Instance root object and safe descendants are
  writable.
- Six exact operation resources have explicit artifact owners.
- Twelve software/product resources remain immutable.
- The effect taxonomy contains exactly seven classifications.
- Windows BAM state for the exact principal and Factorio executable is the
  only initial external disclosure.
- DirectInput and NVIDIA effects are not accepted.
- External effects are never permit resources.
- Any unexpected resolved external mutation is Fail.
- Any unresolved target or observation gap is Inconclusive.
- Pass requires a separate human-reviewed hash-closed packet and grants no
  authority.

The canonical Gate 4A policy file SHA-256 remains:

```text
5840b701801454cdc75f99203d1230bf52e07c4f9c45f02be2f5f35b01157215
```

Its internal policy digest remains:

```text
6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
```

## Authority boundary

This implementation adds no public command, permit issuer, process execution,
Factorio execution, Setup, credential, network, Steam, signing, publication,
or Safe-beta authority. The active WorkUnit remains open for review and
closeout. Candidate work cannot begin until canonical policy promotion and
`main` ancestry synchronization are complete.
