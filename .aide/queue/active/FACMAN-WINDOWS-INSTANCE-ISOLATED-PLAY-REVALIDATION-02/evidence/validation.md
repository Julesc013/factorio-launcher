# Validation

## Accepted source and qualification

- FacMan source:
  `2c393acf838dd432d37f8acce50d01f91bfd28ca`
- Universal Launcher:
  `7fc25340623131ba86c08dca4fb8a43b18a4520d`
- Universal Setup:
  `3048128963dc718a7c38c1cfcdda9e813a23b0db`
- remote-source-closure report SHA-256:
  `3ab446b6400f212710190e4cc4890877fdedc7f7335f8d14f121f582b8f0a73d`
- qualification digest:
  `99aee276b2968e493f7830ee0cf949efbcd4b0d843e0e93abe8729f13454d210`
- qualification binding SHA-256:
  `c2313f2940da1072f7fc115fe90b13930e26e12e75bc1135c85783a128e830f0`
- qualification report SHA-256:
  `bb29004f443d5a2b92e3370bcf37b157575610ea0d265d55d2f4524d8eca429c`

## Stage-only handoff

- staged-candidate digest:
  `f7ef4783dd153b1445ec3cd9882134fc0ccb14a19fe3494186b7fe95b721de9d`
- staged-candidate file SHA-256:
  `31397e9d35d33a0e11b60470dedb0939950c69a9a735501f9c77a638d30056e8`
- coordinator config SHA-256:
  `5f67915198777d73dc479e05340f17aafba2b43004a1072332f6908daa5e961a`
- artifact manifest SHA-256:
  `a936bc9f33f811d564c0dc8121591b0bf59bb682de741782fada6b9176a81ece`
- exact copied qualification SHA-256:
  `c2313f2940da1072f7fc115fe90b13930e26e12e75bc1135c85783a128e830f0`
- final-workspace InstanceSpec digest:
  `4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79`
- final-workspace InstanceBinding digest:
  `5b47371af7a87a220aceba7ac2718826aad2c087b9a6bfc9102cd943254701c3`
- final-workspace readiness digest:
  `4fdd3cb2ca3ae262d1093a928294661981a93bb357b0e5b6596a7f270a583567`

The sealed config reloaded successfully through the coordinator's read-only
`validate_config` path. Its exact workspace, qualification, staged binding,
operation identifiers and five false authority fields agreed.

## Boundary

- coordinator stage: `pass`
- coordinator prepare: `not_run`
- Factorio execution: `false`
- baseline capture: `false`
- observer capture: `false`
- permit issuance: `false`
- human evidence or verdict: `false`
- route or authority promotion: `false`
- policy, Setup mutation, signing or publication: `false`

## Repository closeout validation

- target-truth and AIDE compaction tests: `24/24 pass`;
- promotion profile: `555 tests`, `0` failures, `0` errors;
- required-blocked skips: `0`;
- unknown skips: `0`;
- optional skips: `6`;
- unsupported symlink skips: `2`;
- strict validation against the exact provider checkouts: `pass`;
- project-state generation and validation: `pass`;
- AIDE Lite validation: `pass`;
- `git diff --check`: `pass`.

An initial promotion invocation under the offline sandbox identity could not
read the elevated task-owned provider clones because Git correctly rejected
their different owner. The identical profile was rerun under the same Windows
identity that created and qualified the clones; that exact-pin run is the
passing 555-test result above.
