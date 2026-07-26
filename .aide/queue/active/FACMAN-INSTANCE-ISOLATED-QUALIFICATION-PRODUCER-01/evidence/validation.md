# Validation

Status: PASS.

No Factorio process, WPR capture, permit, human verdict, route acceptance or
authority promotion is allowed in this WorkUnit.

Observed local results on Windows x64:

- focused producer/coordinator Python suite: 8 of 8 passed;
- complete supported Python suite: 527 passed with 9 expected
  optional/platform skips;
- fresh Visual Studio 18 2026 x64 native graph: 55 of 55 CTests passed;
- strict validation: 300 schemas and every policy, security, package, release
  and three-repository lock check passed;
- portable AIDE Lite validation: PASS;
- both frozen policy digests remained exact.

The fresh native build used MSVC `19.51.36248.0`, Windows SDK
`10.0.26100.0`, and an initially absent task-owned build root under the local
temporary directory.

The required-package wrapper correctly refused to operate while the source
checkout was dirty before commit; that refusal was not bypassed. After the
implementation was committed as
`7a32f5316ac08b48c648499c0104c958f7344691`, CMake regenerated the exact
source identity, rebuilt the graph, and the clean-checkout Windows package
proof passed 14 of 14 required obligations with zero skips.

Pull request
[`#83`](https://github.com/Julesc013/factorio-launcher/pull/83) bound
the exact reviewed head
`7592e99cab718cac38089b7c6d315594619658cf`. Every duplicated hosted
appkit, C/C++, C#, Linux coverage/native, macOS archive/native CLI, policy,
Python, Windows package and CodeQL check passed. The reviewed change was
merged to `dev` as
`426d13cc2f68782b40eae66f0fb0621a607b7998`.

The remaining boundary is not producer implementation. It is the separate
remote-only candidate qualification and then the human-controlled real-Play
revalidation.
