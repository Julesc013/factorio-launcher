# Candidate activation

## Disposition

`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-CANDIDATE-01` became active only after
the Windows Instance-Isolated Play policy completed its reviewed closeout,
policy-only canonical promotion, ancestry-only synchronization, and exact
synchronized-`dev` workflow proof.

## Bound policy

```text
policy_id     facman.windows-instance-isolated-play.2.0.77.x64.v1
claim_id      factorio.windows_instance_isolated_process_tree.v1
policy_digest 8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
platform      Windows x64
Factorio      2.0.77 standalone non-Steam
intent        menu
isolation     instance_isolated
```

## Integration chain

```text
implementation PR       67
implementation dev      28495de937f1184dacc745f41dcac675756ef931
closeout PR             68
closeout dev            5267d17b8fc8095d31448044dded6d42eda75fda
promotion PR            69
canonical main          f9670ed6afedcbf9b5c297e8ead478cd3aeea4c5
synchronization PR      70
synchronized dev        c49a9b5cf1a660e63730cae02778af3e00894a87
shared tree             d7cbe1339423b1dcda2763231aa9e99d4a59476a
```

`main` is an ancestor of synchronized `dev`; the two branches had the same
tree at the synchronization boundary.

## Exact synchronized proof

```text
CI                30147917473 PASS
code security     30147917492 PASS
security policy   30147917475 PASS
```

The schema was unchanged by the ancestry-only synchronization and remains
bound to exact canonical-main schema run `30147122303`.

## Authority boundary

Activation starts implementation work only. It does not add or promote:

- a public `instance.play` route;
- product permit issuance;
- a real Factorio run or human verdict;
- Setup or installation mutation;
- credentials, networking, Steam, signing, or publication;
- authority for external OS or driver writes;
- a hermetic or whole-host immutability claim;
- playability or Safe beta.

The candidate must remain unable to record its separate human verdict.
