# Gate 4C live privilege-boundary validation

The committed harmless probe was run from a normal interactive desktop
PowerShell against the exact local repair build. Windows displayed one UAC
consent boundary for the observer-only broker.

## Bound evidence

```text
probe ID                 gate4c-privilege-probe-live-02
probe digest             e74f276c6ee43d2c436b09bade4d265fd0165903f963ae09f7f0e8e61bad105b
broker response digest   8ded3340f2d6de60d83041e6a480129294e44d4e5c3f27cc76b2a26905fd4c2d
source evidence SHA-256  e8e614cf37feab54efb9f52133e35025984d38bdc35b376d55139bc734c5f841
frozen policy digest     6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
hosted matrix revision   97735a42aebbba818cebd01a20da98693b293d44
```

## Independently verified result

```text
outer schema                         PASS
outer canonical probe digest         PASS
authenticated response schema        PASS
authenticated response digest        PASS
not-applicable capture binding        PASS
coordinator integrity                 medium
observer broker integrity             high
Windows principal/session binding     PASS
mutual process and binary identity    PASS
WPR started                           false
Factorio started                      false
coordinator process terminated        true
broker process terminated             true
WPR after probe                       idle
candidate processes after probe       none
```

The probe does not establish a Factorio verdict and does not promote product
Play, permit issuance, persistent broker, Setup, credential, networking,
signing, publication, or canonical-main authority. It completes the remaining
interactive process-boundary proof required before reviewed repair closeout.
