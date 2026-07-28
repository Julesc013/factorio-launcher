# Observer-start repair closeout

Closed: 2026-07-24T08:08:48Z

## Disposition

```text
PASS
```

The bounded Gate 4C observer-start repair is implemented, reviewed, tested,
live-proven without Factorio, and integrated into `dev`.

## Integrated identity

```text
Pull request          #62
Reviewed head         c7c90554295f5de46447c013d7d0fea09dd03b22
Merge revision        1a142896328051385a3e44a47f5116c3d0d01bbb
Frozen policy digest  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
Observer provider     gate4c-etw-file-registry-process.v5
Self-test schema      factorio.gate4c_observer_self_test.v5
```

PR #62 contained four atomic commits:

1. preserve exact observer-start diagnostics and fail-closed ordering;
2. repair the missing provider-validity contract and invalidate v4 evidence;
3. record the passing elevated direct/native observer-start proof; and
4. isolate the Windows test platform without mutating process-global
   `os.name`.

## Proof

- The original pre-WPR failure was reproduced directly and through the native
  supervisor with exact stderr.
- Root cause was the absent `valid` field in
  `observer_provider_identity()`.
- The corrected direct elevated probe passed.
- The corrected native-supervised elevated probe passed.
- WPR became active before the native-supervised helper process boundary.
- Both probes reported zero live dropped events, saved ETL traces, and returned
  WPR to idle.
- Native job containment and process-tree cleanup completed.
- No permit was issued and no Factorio process started.

The append-only external artifacts remain under:

```text
E:\Temporary\FacMan\
  FACMAN-HERMETIC-STANDALONE-PLAY-OBSERVER-START-REPAIR-01\
```

## Validation

- focused Gate 4C Python: 58 passed with two expected platform skips before
  the final portability regression;
- complete local Python suite: 434 passed with 314 expected skips;
- Windows Debug native CTest: 49/49 passed;
- focused Release native CTest: 2/2 passed;
- strict schema, security, policy, contract, and truth validation: passed;
- portable AIDE Lite validation: passed;
- exact final head hosted Linux, Linux coverage, macOS, AppKit, Windows package,
  C/C++, C#, Python CodeQL, and security-policy matrices: passed;
- structured commit range and diff checks: passed.

Hosted workflow runs for the exact final head:

```text
CI               30074942673 and 30074944973
Code security    30074942684 and 30074944947
Security policy  30074942685 and 30074944950
```

## Authority boundary

This closeout does not:

- issue a product permit;
- start Factorio;
- record a new human verdict;
- enable public Play;
- change the frozen policy;
- enable Setup, credentials, networking, Steam, signing, or publication; or
- promote Safe beta or canonical `main`.

The next WorkUnit is a fresh evidence-only Gate 4C attempt. It must not reuse
attempt-01 baselines, plans, permits, capture tokens, or verdict artifacts.
