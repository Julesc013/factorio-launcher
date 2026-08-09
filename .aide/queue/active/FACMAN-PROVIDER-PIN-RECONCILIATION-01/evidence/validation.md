# Validation evidence

## Integrated identity

```text
PR                       127
reviewed head            39553f143f760c9e8726cc23296bce6ff8fa3d23
reviewed tree            9630fd3df5300f798f3f3f3c71db5956a8848cc7
dev merge                15a6369222790ef25656156c062d5657c8bf4b1a
dev merge tree           9630fd3df5300f798f3f3f3c71db5956a8848cc7
Universal Launcher       1cafe4054297cc11e02458b83d230db0cd064471
Universal Setup          32488fc13bd2439f9f6e52e83a97f6da345a7650
```

The reviewed head and merged `dev` revision have identical trees. Local
`dev` and `origin/dev` both resolved to the merge revision after integration.

## Exact reviewed-head workflows

```text
General CI                          31174874500  PASS
Provider input/seven-mode proof     31174874481  PASS
Provider SDK consumption            31174874514  PASS
Schema check                        31174874471  PASS
Security policy                     31174874479  PASS
Code security                       31174874485  PASS
Synthetic product TCK               31174874504  PASS
```

## Exact merged-dev workflows

```text
General CI                          31201461796  PASS
Provider input/seven-mode proof     31201461859  PASS
Provider SDK consumption            31201461692  PASS
Schema check                        31201462449  PASS
Security policy                     31201461739  PASS
Code security                       31201463963  PASS
Synthetic product TCK               31201462178  PASS
```

Every hosted workflow completed successfully on attempt 1. The reviewed-head
Windows job passed static and shared Debug/Release native suites (39/39 each),
893 promotion tests, the 18-test zero-skip package proof, WinForms transport
and client smoke, strict validation, static CLI/TUI packaging, shared WinForms
packaging, and byte reproducibility.

The hosted composition proof contained exactly 333 schemas in every Windows
package. Static CLI/TUI packages contained none of `ulk.dll`, `usk.dll`, or
`flb_factorio.dll`; the shared WinForms package contained exactly those three
selected shared runtimes. Static and shared build identities were equal except
for the declared provider linkage.

## Governing digests

```text
workspace_lock.v1.toml
510511d597ef4ff1ce58f198b7d45796d7723411d09ca15f0e87d539445408e3

providers.lock.v2.toml
59376482126a8226bb28c5b5d73e980d21d3081b76bdf10bd5c10297f2462249

successor_play_route.v1.toml
98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632
```

Provider reconciliation is accepted on `dev`. Route v1 remains immutable;
route v2 is dependency-ready but does not yet exist or carry authority.
