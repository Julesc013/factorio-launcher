# FacMan 2.1.14 menu-observation repair 01

Date: 25 August 2026

State: `review_ready_non_authorizing`

## Result

The authorized base-game route completed exactly two supervised Sandbox
process sessions, but neither session satisfied the main-menu criterion. Both
Factorio logs ended with `Closed during loading.` after the fixed 20-second
close delay. Neither contained the exact `Factorio initialised` marker.

The original observer nevertheless returned success because it admitted a
clean process exit, source immutability, and ULK-authoritative Last Run without
checking the menu marker. This checkpoint converts that false-positive into a
bounded regression and repairs only the release-route observer and guest
timing. It changes no FacMan product capability or candidate package bytes.

## Closed execution

The exhausted authorization produced two distinct sessions, operations, and
attempts with clean exit code zero and correct Last Run records. The source
archive remained unchanged across both launches. Machine route disposition is
`Fail: menu_success_criterion_not_reached`; the named human verdict remains
`Inconclusive` until the observer records what was visible.

The second launch and evidence closure expired D3/D4 authority. This repair
does not reactivate it, and no third launch is permitted under the exhausted
grant.

## Repair

The release observer now:

- accepts the menu criterion only when standard output contains the exact
  `Factorio initialised` marker;
- rejects output containing `Closed during loading.`;
- returns a non-success terminal receipt when the process exits cleanly before
  the menu;
- provides a native self-test for both the rejected and accepted cases.

The Sandbox guest now closes each supervised process after 90 seconds and
allows 180 seconds for bounded termination. Historical 2.1.14 evidence reached
initialization after about 57 seconds on a first launch, so this provides a
bounded observation window without opening an unbounded process lifetime.
Failed observer receipts are copied to the declared evidence mapping before
the guest propagates the nonzero exit, preserving route-failure evidence.

## Rebound non-authorizing identities

```text
protected repair base  efa096f1e30eb71f23995876a1435444105d999b
base tree              d2c63767da97dd9381f753a848d6705ea2157a0c
harness source         c501de3151a142d973dc05cace1080b1b917f9d9d5335a73e0c512b71b1883f9
build definition       d6d4e77efce9dec818827d67a1b3032a0a3badc390e40d57946db2b47137a698
guest runner           6d46724ed2690ab91830c9450c37d7103a5578a5ba55b91afacecb94997b1c1c
policy                  e3d6650a3b29a96f2ab53bee92534d71a99b25f123bc93a45e7c24d0cfed5c08
source closure          4badcfcf3d9e57d09e4bb08fe186164b2095c4eafe7aab99ca9adb7536589013
route v3                afe6f61bdf43b2ceb551f45a796421156abdf1aec27273f5fdd327c6f91c0e50
route record            84bb021246d5d9572daf4d77309d1a058fe128cf12e764aad2a93452ecfeb575
```

The alpha.1 package, Factorio archive, executable, providers, and qualified
Sandbox identities remain unchanged. Every source authority field remains
false. After this exact repair is reviewed and integrated, a new narrowly
bounded external authorization must bind the new protected integration head,
observer binary, policy digest, and route digest before another two-launch
attempt. No tag, signing, publication, support, or beta authority is granted.
