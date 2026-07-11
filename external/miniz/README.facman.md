# FacMan Miniz Source Pin

FacMan vendors the source-only Miniz `3.1.2` release for static project
linkage. Product runtime networking and dynamic dependency discovery are not
used.

```text
upstream: https://github.com/richgel999/miniz
version: 3.1.2
commit: 77d0dce8627735138c51770d1799a1ef48f2117d
release_asset: miniz-3.1.2.zip
release_asset_sha256: f0446d863f9c19926ad9483c523fdc42e42b8d4a6a431d27e09d49c79a140d9a
miniz.c_sha256: e2c1aeb66eef9191d8c3feb164db2def2335a61d039bf04ed849f6b042433b30
miniz.h_sha256: b53b62ed122e559b8f679e3cb787a0b0035fe87a58f909da0e44931678f4e85f
license_sha256: 0115478d567121238cf6cc1c0c361926cf07a49d9e4c9e66da97fac6a01646b3
license: MIT
transitive_runtime_dependencies: none
```

The upstream `LICENSE`, README, and changelog are retained beside the exact
amalgamated source pair. FacMan policy code remains responsible for archive
paths, resource budgets, collisions, file types, transactional extraction,
and all product-specific semantics.
