# Validation

Result: PASS for the local promotion obligation profile.

Command:

```text
py -3 tools/dev.py test release --full --obligation-profile promotion
```

Recorded results:

- Native test suite: 41/41 passed.
- WinForms build: .NET Framework 4.8 completed with 0 warnings and 0 errors.
- Python test suite: 1,417 tests run with 0 failures, 0 errors, and 9
  classified skips.
- Python skip accounting:
  - optional: 2;
  - unsupported: 5;
  - not applicable: 2;
  - required blocked: 0; and
  - unknown: 0.
- Strict validation passed with 399 schemas, 127 commands, 247 refusal codes,
  and 128 goldens.
- The post-commit GTK remediation suite passed 33 focused package-proof,
  classic-shell, generated-metadata, and live-shell tests. The strict gate also
  passed after the repair, including source-size and manual-JSON budgets.

Hosted feedback:

- PR 227 run `33523786560` built and tested the Linux native and GTK targets,
  then failed the external AT-SPI lookup because the probe retained the old
  `FacMan GTK 3 C1 Preview` title while the binary used generated alpha.5
  product metadata.
- The repair now passes the generated title into the external probe and emits
  a schema-valid, request-correlated `facman.transport_response.v2` fixture.
- PR 227 merge ref `a5cc990d0a684a24f681eed9a0f10a2e09071d54`,
  associated with repair head `f6546d2d24bce1fa198f7e923d0a6a73e9384356`,
  has the identical tree `b6cf55caffdeeeacd3a1856e30143dba727c0d4b`
  and passed `linux-native` job `99929032838` in run `33529589182`, including
  the generated-title GTK build, package, runtime, and external AT-SPI proof.

The passing command establishes local promotion qualification only. It does
not supply the separate manual hosted Windows/macOS/Linux product-candidate
bundle, cross-platform GUI semantic evidence, human accessibility verdicts,
signing or notarization, a release tag, publication authority, or support
approval.
