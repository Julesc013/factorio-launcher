# Final repaired qualification chain

The accepted source composition is:

```text
FacMan             ab159b8ced48ecbaaa1d8f37bb1b4687c6b4c679
Universal Launcher 7fc25340623131ba86c08dca4fb8a43b18a4520d
Universal Setup    3048128963dc718a7c38c1cfcdda9e813a23b0db
```

The final empty-root closure passed:

```text
report SHA-256      e6f9be1c563a06a8ef28a005e982e92dc52b41532b98b4cd2d08881dce1df56f
package SHA-256     239a0c56751195bc3d1858ae5dae722859b2abfd1b7c1f9f806154613bd9301e
provenance SHA-256  b2db0c038edfa8e34804741c0eb2b03820b9b0786426068be07f3b024f6885d5
```

Qualification-04 passed:

```text
qualification digest  49732ad3a785a1341f642b9cfd99c01a78bbb199f6a3ef8b88b8a7acd79d9868
report digest         04efedc73010b6dc09c9c92c9b2f6f7499db9c7a23f5696e2bc1baaa772a137f
binding SHA-256       ea30efc379fc026d64e6a9611f941d2a68cf3caf527088b75f370d27af5271cd
report SHA-256        df9ee8e9730626fd1e9c209ecf56bff77652bea29d97a84359e18e18fa8520a1
```

Only this final repaired qualification entered revalidation-03. The first
qualification-04 remains `superseded_before_stage`.

The stage-only handoff produced:

```text
files                    16
bytes                    63,878,491
reparse points           0
qualification filename   qualification-binding.v3.json
v2 filename              absent
staged-candidate digest  b2e8335fa372e8f796af939e426a0cc3c7f98a68497e8fe9326e8b7f1da5a35c
```

Qualification-04 meets every closeout checklist item and grants no authority.
