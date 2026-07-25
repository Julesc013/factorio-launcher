# Policy implementation validation

## Local result

```text
Windows instance-isolated policy validator       PASS
Canonical policy digest                           PASS
Frozen Gate 4A policy byte identity               PASS
Focused policy/truth/architecture tests           PASS (42)
Schema metaschema and repository validation       PASS (292 schemas)
Native Windows Debug configure/build              PASS
Native Windows Debug CTest                        PASS (50/50)
Complete Python discovery suite                   PASS (466; 315 expected skips)
Strict repository validators                      PASS
Portable AIDE Lite                                PASS
Project-state generation and validation           PASS
Source formatting                                 PASS
```

The first complete Python invocation correctly refused its package-runtime
lane because no external native artifact had yet been built. The native tree
was then configured and built under the recorded task root, and the complete
suite passed against that exact artifact.

## Validation root

All build products and logs are outside the repository:

```text
E:\Temporary\FacMan\FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-POLICY-01
```

The CMake configuration binds:

```text
D:\Projects\Universal\universal-launcher
D:\Projects\Universal\universal-setup
```

Both sibling repositories remained read-only and clean.

## Frozen identities

```text
Windows instance-isolated policy
  8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432

Gate 4A hermetic policy file SHA-256
  5840b701801454cdc75f99203d1230bf52e07c4f9c45f02be2f5f35b01157215

Gate 4A hermetic policy digest
  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
```

## Boundary

No WPR session or Factorio process was started. No permit was issued. No
runtime, public command, Setup, credential, network, Steam, signing,
publication, or product authority was added.

## Exact reviewed-head proof

PR #67 reviewed implementation head
`c25491e5250f80d9b1f9813ddf37910315bcc96c` passed both push and
pull-request workflow sets:

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `30144796327` | `30144805820` | Pass |
| Code security | `30144796337` | `30144805795` | Pass |
| Schema check | `30144796328` | `30144805851` | Pass |
| Security policy | `30144796329` | `30144805806` | Pass |

PR #67 merged with exact-head matching into `dev` revision
`28495de937f1184dacc745f41dcac675756ef931`. Its exact merged-state
proof passed:

| Proof | Run | Result |
| --- | --- | --- |
| CI | `30145199265` | Pass |
| Code security | `30145199294` | Pass |
| Schema check | `30145199268` | Pass |
| Security policy | `30145199267` | Pass |

## Clean pinned reconstruction

One task-owned temporary workspace used fresh detached clones at:

| Repository | Revision |
| --- | --- |
| FacMan | `28495de937f1184dacc745f41dcac675756ef931` |
| Universal Launcher | `7bd4425f0c35414f738159b45d8bec42edf70235` |
| Universal Setup | `3f8489275077347c2918f3bb03614ec6431362ff` |

All three repositories configured, built, tested, and passed strict checks.
FacMan additionally passed AIDE Lite and its complete Python suite. The
repository-owned serial matrix completed in 455.2 seconds. The detached
source checkouts remained clean and exact at their pins.

The earlier exact implementation-head reproduction also passed the policy,
schema, focused, strict, and AIDE checks at `c25491e`.

## Closeout boundary

The policy is accepted on reviewed `dev` and is ready for a separate
truth-only closeout and later canonical policy-only promotion. No WPR session
or Factorio process was started. No permit was issued. No runtime, public
command, Setup, credential, network, Steam, signing, publication, or product
authority was added.
