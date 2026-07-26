# Validation

Result: `PASS` locally; hosted validation pending publication.

Exact provider inputs:

- Universal Launcher: `fbb0cc87a14e8e4b26d74088a791dc83ebd4337d`
- Universal Setup: `3f8489275077347c2918f3bb03614ec6431362ff`
- source-closure merge: `28eeb2cfb3797c9614a7e8e5b1922f333a7f828a`

Authoritative Windows validation:

- Visual Studio 18 2026 Debug configure/build: PASS
- native CTest: PASS (`52/52`)
- complete Python suite: PASS (`501`, `9` platform/profile skips)
- Windows portable package artifact tests: PASS (`23`, `2` expected profile skips)
- strict validation: PASS (`296` schemas)
- AIDE Lite portable validation: PASS
- application composition validator: PASS
- diff hygiene: PASS

Focused controls:

- missing, unknown, failed, recovery-required, retired, uninstalled, and
  unsupported lifecycle evidence cannot become active;
- only exact `active` plus `verification_status=pass`, a verification identity,
  a state revision, and a fresh ULK reference graph remains reference-fresh;
- direct structural imports remain explicitly `unknown` and launch-ineligible;
- stable no-follow config reads reject hard links, unsafe paths, oversize,
  incomplete reads, and identity changes;
- protected user-data roots are captured once by immutable application
  configuration and passed into preflight;
- denied admission transformation is exact to `run.execute` and the three Mod
  Portal network commands;
- shared candidate storage carries a generic marker rather than a historical
  WorkUnit identity;
- current player messaging reports absence of an accepted exact route.

Claim boundary:

- Factorio execution: `false`
- permit issuance: `false`
- authority promotion: `false`
- policy change: `false`
- writable-resource widening: `false`
- package publication/signing: `false`
