# Validation

Status: PASS.

The exact repaired source set was reconstructed from three empty `--no-local`
GitHub clones under this task-owned local observation root:

```text
C:\Users\Jules\AppData\Local\Temp\FacMan\FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-01
```

The three pins existed, were reachable from the required canonical remote
refs, were checked out detached at the exact revisions, had no object-store
alternates and remained clean after validation:

```text
factorio-launcher
  b874a40ccba747565c34b726bd6c0d94c9dc1be0
  ancestor of origin/dev

universal-launcher
  7fc25340623131ba86c08dca4fb8a43b18a4520d
  ancestor of origin/main

universal-setup
  3f8489275077347c2918f3bb03614ec6431362ff
  ancestor of origin/main
```

Generated runtime build identity:

```text
facman=b874a40ccba747565c34b726bd6c0d94c9dc1be0;
universal_launcher=7fc25340623131ba86c08dca4fb8a43b18a4520d;
universal_setup=3f8489275077347c2918f3bb03614ec6431362ff;
source_dirty=false
```

The build used Visual Studio 18 2026 x64, MSVC `19.51.36248.0` and Windows SDK
`10.0.26100.0`. The exact uninterrupted remote-clone build completed
successfully.

Focused native validation: 6/6 passed.

Focused Python validation: 92/92 passed, with two expected sandbox skips where
the validation environment could not create symbolic links.

Strict validation: PASS, including 298 schemas and exact frozen policy
digests:

```text
hermetic
  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2

instance_isolated
  8d8189a9e8fc9ff7e479f7dda1adf0ea516bed2878046468022b2da8355e2432
```

Project-state validation: PASS.

Portable AIDE Lite validation: PASS.

## Exact candidate artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `facman_gate4c_verdict_harness.exe` | 1,265,664 | `9a2048bd0b46fd594c546fc0dc8e7156dafdd99d1eeaf2dd96b0e8a16aaa3b93` |
| `facman_hermetic_play_candidate_smoke.exe` | 707,584 | `bfb675fa7b5c20a7babb8bda1f2ea4411879fd44f2e9bf8424fc53c4acf9d4ab` |
| `facman.exe` | 3,583,488 | `c48b9d77e51c9889c57d0fcb92ba0ff7fd5a702ed5f9e93994efb28bc8a33929` |
| `facman_isolation_probe.exe` | 186,368 | `eef55e8e02cd3be2231dd15f011d33e9728539cd8866734836a7b3a8b96cf86e` |
| `facman_operation_permit_smoke.exe` | 262,144 | `67cdcdb3b710dbeee97a5b9db81d2ec1494df21660f6550c0ae276fa54bcaffc` |
| `flb_factorio_launch_permit_smoke.exe` | 1,018,880 | `a58eafad89666ba3000a9b390379a02395b7b909718fb88586992ad1d6253a2f` |
| `facman_isolation_lock_smoke.exe` | 241,152 | `a0efdf734876c9927cfbb16a5e79576fd4b3cad187684dc7f28c2895c6f43ca5` |

This PASS qualifies only the exact source/build/artifact reconstruction. It is
not a human Play verdict and does not issue a permit, execute Factorio, accept
a route or promote authority.
