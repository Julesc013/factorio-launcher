# FacMan 2.1.14 route permit enforcement 01

Date: 26 August 2026

State: `review_ready_non_authorizing`

## Result

The release route now refuses process dispatch unless the Sandbox guest supplies
a fresh, correctly bound HMAC permit envelope and custody record. A valid
permit is atomically and durably claimed before dispatch; missing, malformed,
stale, wrong-context, replayed, concurrently reused, or crash-claimed permits
dispatch zero processes.

The qualified Sandbox builder now validates all declared isolation controls,
including `<VGpu>Disable</VGpu>`, and binds exactly five mapped folders with
four read-only mappings. The guest passes the full release harness context
instead of the former 13 option/value pairs.

No Factorio executable or Windows Sandbox configuration was launched while producing this checkpoint.

## Two-phase authority topology

Route v4 is deliberately non-authorizing. It records the only acceptable later topology:

1. A future host-side authority binds permit one to the fresh protected source, package, providers, archive, host, policy, route, observer, operation, attempt, action, and launch-one ordinal.
2. The guest validates and atomically consumes permit one before launch-one dispatch.
3. Launch one must emit terminal evidence and a terminal-ready receipt.
4. A host-side safety actor must revalidate the terminal evidence, identities, freshness, isolation, and closed higher authorities.
5. Only then may a distinct permit two be issued for the launch-two ordinal.

The guest refuses any launch-two permit material that exists before launch
one. Route v4 forbids pre-issuing both permits. It does not itself issue either
permit, so a later reviewed authorization packet must supply the exact
external authority and fresh inputs.

## Sandbox and custody boundary

The WSB contract requires networking, clipboard, printer, audio input, video
input, and vGPU to be disabled. The writable evidence mapping is separated
from the read-only candidate, archive, harness, and permit-source mappings.
The guest copies permit material into a session-local custody directory,
validates strict digests and schemas, and exports only bounded issue, consume,
refusal, freshness, and terminal receipts.

## Bound non-authorizing identities

All source identities below use the route checker's canonical LF normalization where applicable:

```text
protected base commit   e73d778173be283d47925fa055ba1aae7b82fb28
protected base tree     a1f96dd4fe2cf5d3eb69e428e2721d9356e8fe24
harness source          8d9ca65dc68dcfba573be4e7f1dbf2273c7b96d057a5110524c5bb45755760ac
permit gate source      a23279ad56bad7ffe51fe6a00af012ff777e59ffb928db3aa8b1b4018efa3275
permit gate header      b5f7b4c04b758d9452e76863208357854c37c12eeedeee6b3f2fdf0b1981f7df
observer composite      dc1bcb3d7e56db07ad83fe653fffdc3cef28fd40c94636b8ca2f658d24fc487a
build definition        3494443c338d4643e285169adcd06d98d63b3373eb0f295dbd94061f2c0278e7
guest runner            25b93252925547c38f7cf35f3ff3f367b8aafa6bc1c8c2117098463118e88da3
bundle builder          c12cd88b571d8be0777de629a13a67d8f29fa6a6e223fc4d8ef452a6061fadff
policy v2 definition    cb0ec38304775a40aeed153708b7115c4df0517bd7b99bc4b6b31a81f9374e58
route v4 definition     826fc8ef495f238ad6ad45932e3abe61acfc7e5d93e4142aa74391b5f918c266
```

The frozen route v3 and policy v1 remain byte-identical historical inputs.

## Queue reconciliation

- `FACMAN-0.1.0-ALPHA.1-RELEASE-SOURCE-01`, `FACMAN-AIDE-COMPACT-HISTORY-V1-01`, and `FACMAN-PROVIDER-PACKAGE-MANIFEST-IMPORT-01` are mechanically closed with durable integration evidence.
- `FACMAN-ULK-SESSION-PIN-ADOPTION-01` is superseded by the already integrated PR #146 result.
- `FACMAN-2.1.14-RELEASE-ROUTE-01` is superseded for execution by this v4 repair; its exhausted v3 evidence remains historical.
- Managed-install and autonomous-governance work remain finite future epics with their existing owners, dependencies, and entry conditions; they are not activated by this WorkUnit.

The strict profile is locally green. Protected review and hosted checks remain mandatory, and every merge, tag, signing, publication, support, and route-execution authority remains false.
