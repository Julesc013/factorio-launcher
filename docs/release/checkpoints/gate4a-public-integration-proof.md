# Gate 4A canonical public integration proof

## Disposition

The Gate 4A policy is canonically accepted and the separately scoped Gate 4B
candidate WorkUnit may begin.

This checkpoint binds the policy-only closeout, canonical promotion, and
ancestry synchronization without changing the frozen policy tree:

| Boundary | Pull request | Revision |
| --- | ---: | --- |
| Reviewed policy implementation | #47 | `cf674d852e16ceb237ab83dc9254b37b0d900aa2` |
| Policy integration on `dev` | #47 | `51f4fc24c9164762a88b92b4f865b04fe9256d4b` |
| Policy closeout head | #48 | `d46aab915432a47cfdcc520138bbbbf70b4311fb` |
| Policy closeout on `dev` | #48 | `cb7b951b1fc847c1bc1c0a56bff07763a4044d13` |
| Canonical policy-only `main` | #49 | `ca9ca5db443544868f3add2802593b7073a5cb20` |
| Synchronized `dev` | #50 | `0b87833252330b8c60df8b096a322fd481a18589` |

The canonical and synchronized revisions share tree identity
`c65b6e580385a9421e00ba145ce08d814568ed8e`. `main` is an ancestor of `dev`.
PR #50 changed ancestry only; it did not alter the accepted policy tree.

## Frozen law

```text
policy  facman.hermetic-standalone-play.2.0.77.windows-x64.v1
claim   factorio.hermetic_process_tree.v1
digest  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
```

The canonical label **Hermetic standalone** means process-tree hermetic under
the policy's exact writable and protected-resource model. It does not claim
whole-host immutability.

The candidate remains limited to Windows x64 Factorio 2.0.77, a Wube-owned
standalone non-Steam application tree, a fixed local NTFS volume, one
FacMan-owned instance, an explicit empty mod lock, `menu` intent, and
`hermetic` isolation. It cannot weaken the 13 writable-resource, 18 protected
or disclosed-resource, 31 evidence-requirement, two-observer, 29-case, and
three-verdict policy spine.

## Closeout proof

The PR #48 closeout head passed both its push and pull-request workflows:

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `29848919084` | `29848923709` | Pass |
| Code security | `29848919045` | `29848923567` | Pass |
| Security policy | `29848919052` | `29848923639` | Pass |

The exact closeout merge on `dev` passed CI `29849914549`, code security
`29849914687`, and security policy `29849914655`.

## Canonical `main` proof

PR #49 promoted the exact closeout tree without a promotion-only content
commit. Its head passed:

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `29850902593` | `29850906191` | Pass |
| Code security | `29850902581` | `29850906373` | Pass |
| Schema check | inherited | `29850906413` | Pass |
| Security policy | `29850902606` | `29850906192` | Pass |

The exact canonical `main` revision passed CI `29851839515`, code security
`29851840822`, schema check `29851840768`, and security policy `29851840676`.

## Synchronized `dev` proof

The PR #50 synchronization head passed:

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `29852774687` | `29852778523` | Pass |
| Code security | `29852774689` | `29852778712` | Pass |
| Security policy | `29852774831` | `29852778832` | Pass |

No separate schema workflow was required for the ancestry-only synchronization:
its tree is identical to exact `main`, whose schema run `29851840768` passed.

The exact synchronized `dev` revision passed CI `29853752527`, code security
`29853752922`, and security policy `29853753034`. That CI includes Linux,
macOS, Windows, coverage, sanitizers, fuzzing, packaging, reproducibility,
the full Python suite, and strict validation.

## Authority boundary

This public integration grants no:

- product permit issuance;
- process execution or `instance.play` route;
- real Factorio run or human Play verdict;
- setup, installation, instance, credential, network, or host mutation;
- alternative launch intent, Steam route, or broader candidate class;
- signing, publication, playability, or Safe beta promotion.

`FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01` is active only as the next
implementation boundary. `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01` remains
separate and is the only lane allowed to record the later human result.
