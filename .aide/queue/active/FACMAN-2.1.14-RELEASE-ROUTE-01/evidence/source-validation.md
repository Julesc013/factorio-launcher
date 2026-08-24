# Source validation

The source slice freezes the exact, non-authorizing Factorio 2.1.14 base-game
Windows Sandbox policy and immutable v3 route at protected base
`41dce656d6e75d9991a101c71b3a7683db873bb3`. It does not dispatch Factorio or
activate D3, D4, route capability, tagging, signing, publication, support, or
Setup mutation outside Sandbox.

Exact bound inputs:

- product source/tree: `8362ddc55cbb98b538f4af410819c9503604ef99` /
  `859695fdcaead2e5e11c5454976432df13cacc1a`;
- hosted package SHA-256:
  `95d5836effa1494d0e976dc4937c198085a61fa30350e7e9f66667c8ffb0a70f`;
- ULK/USK: `5479939ca5cbc9ee0f901608a92012778b4752ae` /
  `d2a2aae7e61c47035c92334b0522143b4fea3880`;
- base-game archive SHA-256:
  `4f2875cb5c1325a1fcd21b2d37248d508dc36f51ddeef7406ca96788773b872f`;
- Factorio executable SHA-256:
  `0ee725652cfa340008d793bece687aea112475599da01521de05413bdf792695`;
- clean Windows Sandbox receipt SHA-256:
  `8e7fb8ac781c7cad00a9504ae488069b08c39fbb48b06a88b04ba0110c17e08a`;
- release-route observer source/build/guest/bundle SHA-256 identities:
  `55b4897cf5f5f20de64dac5d67f639073ebedf0ccaf339fca581b57cfcd9fcb8`,
  `39d83fb6ec156386110d3e12d6ff3fb06e56569ddbd3d1847791922ecb8fd5fb`,
  `2d1e80a1f7c934b9dc9a545c3346972e1bd899b837dd8af6cae96a1a93beed5f`,
  and `916fd8ab69f6a44725f91610cc9e338fb18e4f9340be964169bed98a4f163f42`.

The observer binary identity remains externally assignable only after the
reviewed source is integrated and built. The historical engineering harness
is intentionally not reused because its executable binding is for the
superseded Space Age route.

Validation completed in the isolated exact-base worktree with the repository's
pinned Python 3.11 environment and exact ULK/USK source roots:

```text
factorio-2-1-14-release-route-check    PASS
factorio-2-1-14-route-packet-check     PASS
required refusal controls             PASS
focused regression tests              137 PASS
schema validation                      365 PASS
source/release/route validators        PASS
release-route observer MSVC build      PASS
wrong/accepted acknowledgement probes  refuse before dispatch as expected
strict exact-provider validation       PASS
AIDE Lite                              PASS
generated metadata/plan/project truth current
git diff whitespace                    PASS
```

The initial broad schema run under Python 3.14 failed only because that
interpreter lacks the pinned development lock. The exact pinned Python 3.11
rerun passed all schemas. The first strict run passed every gate except a
stale validator that did not recognize the new post-alpha route phase; its
bounded phase transition was added, focused-tested, and the complete strict
rerun passed.

The source slice is ready for exact-head review and protected integration.
Only after that integration may the external one-use route permits be
materialized and negative controls rerun before dispatch.

The pre-integration observer build produced SHA-256
`9a206ef54d2db8e23dfc96f9ecdf4a247f033059646a93c0b93f17b0c2adfe8d`.
It is only a compile/refusal receipt: the final observer binary is rebuilt and
rehashed from the accepted protected merge before any permit is issued.
