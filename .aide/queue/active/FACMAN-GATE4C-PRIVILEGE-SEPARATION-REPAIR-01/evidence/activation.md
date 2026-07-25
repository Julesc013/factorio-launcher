# Gate 4C privilege-separation repair activation

Activated: 2026-07-24T10:24:58Z

## Entry evidence

```text
Dev revision           934d4fcca2d3749f1a9710186afcf1fe294f0dc8
Frozen policy digest   6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
Observer provider      gate4c-etw-file-registry-process.v5
WPR state              idle
Verdict 02 baseline    not started
Verdict 02 permit      none
Verdict 02 Factorio    not started
Verdict 02 verdict     unset
```

## Confirmed defect

The current verdict procedure elevates the native harness because its Python
observer children must control the WPR kernel logger. The same harness then
uses the ordinary Windows process supervisor, which calls `CreateProcessW`
without an alternate primary token. The candidate does not bind or prove the
integrity level of the coordinator or Factorio process.

## Repair ceiling

This task may produce only a verdict-only, one-shot observation privilege
boundary. It cannot create a public Play route, general elevated command
surface, persistent service, or product privilege-broker authority.

The later player-facing `FACMAN-WINDOWS-OBSERVATION-BROKER-01` remains a
separate post-verdict product task.
