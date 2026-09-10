# Validation

Result: PASS for the final Alpha.5 candidate-truth closeout and the complete
local developer promotion-equivalent matrix. This is engineering evidence for
the exact already-built candidate; it grants no human or release authority.

## Exact hosted and durable candidate proof

`tools/alpha5_final_candidate_closeout_check.py` passed against the canonical
receipt and against the operator-supplied durable custody root. It verified:

- source topology: main `4683ecd9a1b9ead5eb84be152760d12583da0f0e`,
  dev `488994a81ddb5eb54d541ef3a48b64ca83f67d4a`, shared tree
  `c07938618bc0f533fd12756cba123f54b8592048`;
- successful product-candidate run `33603385303`, attempt 1, with five
  successful jobs and four retained workflow artifacts;
- final hosted artifact `9836639957`, 39,415,203 bytes, digest
  `sha256:1c53c1e1337dced910f8aa88c9d32c9a36a68d5b87dff2cce7172381f386e736`;
- exact 14-file, 47,428,808-byte durable bundle; manifest SHA-256
  `1be3a4ade7370a6c0ed51dc04eff5ce2ad86eb8034393cdaefa961acd8d4a923`
  and `SHA256SUMS` SHA-256
  `a9b8d06fc6d5062b41e68215399680dfa66689e3dacf9d062424f5d1547944b7`;
- payload equivalence for the Windows setup overlay, macOS pkg root, and Linux
  embedded archive; and
- exact sealed resource identity: 600 entries, 2,233,690 expanded bytes,
  content SHA-256 `4c9802f155c24f289c4d005d06b55bf1769cd939dbce62321875d5a21817827d`,
  pack SHA-256 `ce95c45eb588fae9c0baee6199624e64d90cb872e71b6ba9945126c86c9dc10b`.

The current closeout checkout contains one additional documentation resource.
Its developer-build resource identity is therefore intentionally different
from the sealed candidate's 600-entry identity. The validator requires the
sealed candidate bytes and refuses to let tree equality or the closeout commit
inherit the hosted run.

## Repository and build validation

The following passed after all implementation changes:

- 117 focused final-candidate, release, plan, schema, package, source-closure,
  generated-state, and AIDE regression tests;
- 20 dedicated source-closure admission tests;
- `py -3 tools/strict_check.py`, including 401 schemas, 127 commands, 247
  refusal codes, 128 refusal goldens, the three product package TCK profiles,
  security, compliance, architecture, accessibility, release, AIDE, and
  generated-state checks;
- `py -3 .aide/scripts/aide_lite.py test`;
- generated metadata `--check`, project-state validation, and canonical
  plan-view validation; and
- `git diff --check` (line-ending notices only; no whitespace errors).

The final authoritative managed command was:

```text
py -3 tools/dev.py verify-all developer
```

It exited 0 and completed:

- Debug native configure/build and 41/41 CTest cases;
- Release native source-static configure/build;
- Release product shared configure/build and package-proof roots;
- WinForms .NET Framework 4.8 Release build with 0 warnings and 0 errors;
- WinForms transport harness with all 38 cases passing;
- 1,470 Python tests with 0 failures, 0 errors, 0 required-blocked skips, and
  0 unknown skips; and
- the final strict validator pass.

The classified skips were 2 optional, 5 unsupported, and 2 not applicable.
They were the opt-in bounded R37 performance corpus, an optional install-tree
probe whose source-static tree intentionally lacks `ulk_shared`, unavailable
Windows symlink privilege cases, and POSIX PTY tests covered by a separate
Windows ConPTY lane. The product shared build itself succeeded. None was a
required obligation or an unclassified skip.

No Factorio execution, live setup/install mutation, human verdict, signing,
notarization, tagging, publication, support promotion, protected-setting
change, or protected-branch merge was performed.
