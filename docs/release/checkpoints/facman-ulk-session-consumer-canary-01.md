# FacMan ULK session consumer canary 01

Date: 13 August 2026

State: `exact_consumer_canary_pass_pending_review`

## Exact identities

```text
FacMan base       54b188c0b2d4ab62c1d948cd1c548489fbe8c8b7
FacMan canary     2081e11a05c2793c1f54309a5add4ef7dfdd6469
FacMan tree       cebd23dcd6cd4e9c7ba641072417dd2ae84c6500
ULK dev           e6de83ad1e1a2c646d31eb2ca68aa5cddb323b4a
ULK tree          d877bfa3a86158f65705facf757e8700a067d077
ULK package/ABI   1.9.0 / 1.9
USK main          32488fc13bd2439f9f6e52e83a97f6da345a7650
USK tree          12fe757b1fc2ae78768a8cf912d03835f46ca65b
```

The canary is based directly on the current protected FacMan `dev`. It consumes
the exact ULK `dev` candidate through an external conformance lock. The tracked
FacMan ULK pin remains `1cafe4054297cc11e02458b83d230db0cd064471` on
`refs/heads/main`; its lock digest remained
`510511d597ef4ff1ce58f198b7d45796d7723411d09ca15f0e87d539445408e3`.

## Adapter result

`UlkSessionJournalLastRunProvider` uses only the installed public ULK C ABI.
The journal is rooted at the FacMan workspace, rejects relative and unsafe
paths, is bounded to 64 records and 64 KiB output, follows ULK's two-call
caller-buffer law, and keeps the provider immutable after construction.

The projection distinguishes no record, running/nonterminal, authoritative
completion (including unknown exit code), outcome unknown, recovery required,
corrupt record, incompatible future record, and provider unavailable. A backend
presentation query changes revision when the authoritative record changes and
binds the engineering provider identity.

The option is default-off and requires the non-authorizing provider-conformance
mode. Normal builds continue to install the unavailable Last Run provider.
Package, installed-provider, and integration-source identity gates require
`ulk_session_consumer_canary=false`; a rehashed canary identity is refused.

## Exact-head proof

The no-skip observation is retained outside the source tree at:

```text
.task-builds/facman-ulk-session-consumer-canary-01/
  exact-head-evidence-2081e11/ulk-session-consumer-canary-observation.v1.json
SHA-256 ecce97c006898e2a22d35a426818104d9bb853e3827568872a46f61756d781eb
```

Results:

```text
fresh ULK SDK/TCK full phase       PASS, no skips
FacMan source static/shared        PASS
FacMan installed static/shared     PASS
FacMan relocated static/shared     PASS
negative tracked-lock control      PASS (canary refused)
ULK ABI manifest SHA-256           ce17990b20ee3730cb73a709d8a649fdc5234df8b8e9735bf9a6ea0ea992210e
ULK contract bundle SHA-256        b9e39e83dc1ae85755dce4f5f61d23bc438a0e81882313c04ca00f5eff661e4e
required skips                     0
```

The source/installed/relocated tests cover missing, completion, unknown exit,
uncertain, recovery, running, corrupt, incompatible, Unicode/long-path,
bounded-read, restart, multiple-record, and presentation-revision behavior.
A canonical-pin default-off rebuild also passed and recorded
`ulk_session_consumer_canary=false`.

Additional exact-source validation:

```text
strict policy checks                  PASS
focused identity/canary tests         PASS, 43/43
complete Python discovery             PASS, 1003 tests, 329 classified skips
Windows portable CLI package proof    PASS, 14/14
explicit native CLI runtime cases     PASS, 11/11
full Python stderr log SHA-256         76e1f18d824ad3c9da22ed1e276dd899baabe8f13804bb3a9913ebe5c85ecc66
```

The discovery skips are the repository's explicit optional, platform, or
separately provisioned runtime classifications. The six required consumer
canary modes above ran without skips.

## Authority and next gate

Every execution, Setup, provider-adoption, route, signing, publication, and
credential authority remained false. No Factorio process ran. No provider pin,
protected ref, package classification, release, signature, publication, or
support state changed.

The next provider action is a normal human-reviewed ULK `dev` to `main`
promotion. FacMan adoption remains a later exact-pin WorkUnit after that main
promotion; this checkpoint must not be interpreted as canonical adoption.
