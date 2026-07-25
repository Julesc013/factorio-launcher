# Gate 4C Verdict03 activation

Verdict03 is activated only after PR #64 merged the split-privilege repair into
`dev` at `894b203710b8e14055903c0d33a9d3517fb6aa94` and that exact revision passed
CI, CodeQL, schema, and security-policy workflows.

The new attempt must use:

```text
task root
  E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03

coordinator
  medium integrity

observer broker
  high integrity, one-shot, observer-only, explicit UAC consent

Factorio
  medium integrity, validated before primary-thread resume
```

Every observer self-test, quiet-host attestation, preflight, baseline, plan,
permit, WPR capture, technical packet, and human observation must be newly
generated. Verdict01 and Verdict02 evidence is historical and non-reusable.

Activation grants no public Play, product permit issuance, persistent broker,
Setup, credential, network, Steam, signing, publication, or canonical-main
authority.
