# Validation

Result: PASS for the local promotion obligation profile.

Command:

```text
py -3 tools/dev.py test release --full --obligation-profile promotion
```

Recorded results:

- Native test suite: 41/41 passed.
- WinForms build: .NET Framework 4.8 completed with 0 warnings and 0 errors.
- Python test suite: 1,415 tests run with 0 failures, 0 errors, and 9
  classified skips.
- Python skip accounting:
  - optional: 2;
  - unsupported: 5;
  - not applicable: 2;
  - required blocked: 0; and
  - unknown: 0.
- Strict validation passed with 399 schemas, 127 commands, 247 refusal codes,
  and 128 goldens.

The passing command establishes local promotion qualification only. It does
not supply hosted Windows/macOS/Linux package evidence, cross-platform GUI
semantic evidence, human or accessibility verdicts, signing or notarization,
a release tag, publication authority, or support approval.
