# Gate 4C Verdict 03

## Disposition

`Inconclusive`.

The first fresh launch crossed the reviewed authority and process boundaries:

- observer v5 self-test passed;
- preflight had zero blockers;
- protected and writable baselines completed;
- one exact permit was issued and consumed;
- the elevated observer broker reported WPR active before process creation;
- Factorio PID `29512` was verified at medium integrity and started;
- WPR stopped cleanly and reported zero lost events;
- the protected-state comparison completed;
- WPR was idle and the broker, harness, and Factorio processes were absent after the attempt.

The attempt cannot produce `Pass` or a policy-valid `Fail` packet because the
post-run lifecycle packet was not persisted and target resolution was
incomplete. The native harness attempted to persist its lifecycle packet into
the same `candidate-artifacts` directory that already contained the
integrity, privilege-boundary, and translated observation artifacts. The
fail-closed exclusive-create rule refused the collision:

```text
permit_wrong_resource: candidate operation artifact directory already exists
```

The frozen policy makes `Inconclusive` mandatory when target resolution is
ambiguous or the evidence packet is incomplete or not hash-closed. The second
launch was not attempted and no formal human observation packet was recorded.

## Route-blocking protected-state finding

The complete stable comparison also found that protected resource
`installation.selected` changed:

```text
before digest  889eb80ad51af3e13e08274baad934f989d536c4f7bdad41c5b51fc03890990c
after digest   83b9768c6f17f74bf87f57a282df7acca3c2bc0304b4eefdddd1afaff913ad32
```

The after-manifest contains two new directories under the exact protected
installation:

```text
bin/x64/NVIDIA Corporation
bin/x64/NVIDIA Corporation/umdlogs
```

This is not waived by the Inconclusive disposition. A future route cannot pass
until a bounded repair establishes attribution and prevents any candidate-
attributable persistent installation change under the unchanged frozen policy.

## Exact retained evidence

```text
task root
  E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03

operation
  gate4c-verdict03-launch1-20260725a

source revision
  885b9822809c4b3e91e784bdd7e3b8b261533901

policy digest
  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2

observer self-test digest
  67a62c6b6ed637bc002a1c1fe3be8ab46645cd5928d9e6c19b2b2c43b906a206

preflight file SHA-256
  c15c04fa47ff3d1d398c58b95f983de125e0fa371e9730be3afa12845e74872b

baseline file SHA-256
  75ac465c08ecd8a04097050843a6752ec6cc6510e92db9f849d5c08f3008fcfd

session digest
  b04a04e5d6c3ef22e14cce1f48bb020cf320b035f80e40cc282e8bf594189d62

plan digest
  38736cd70515ba9eca3f269bb5691f1592659e7760241fefbb563934599f31e9

plan approval digest
  88d6b4733de4642733cc19ef82a556cb3bf81c5db40515c55b3ccfc371a2e6b9

baseline comparison digest
  ae67a80fcfa6596ac5fe90fbf643db83414f0200c03f0c562e3c9d09ce9d5d98

baseline comparison file SHA-256
  09186c1eb860baa005c88548ae11eac81c0cde256caee8a25321cadeacb81226

ETL SHA-256
  ffd0e7648bc43e08d95c87abc5f1ff016ac55c1168fc07047162aae8e16f56e6

events CSV SHA-256
  37e0684e1aef8a39aece855d90cefa09344a08e55a09f662216e27ec16f64085

translated observation SHA-256
  26126bb98bc7920858f2e213f14da3f4b2ae32bb18ebdfbe3657cc671760deed
```

The full task root remains retained. No cleanup, runtime repair, policy change,
route promotion, or authority promotion occurred in this WorkUnit.
