# Versioning

FacMan product versions, schema versions, and ABI versions are separate
compatibility surfaces.

## Product Version

Canonical product versions use SemVer plus build metadata:

```text
facman-0.1.0+dev.3f12a9d
facman-0.1.0+beta.10471
facman-0.1.0+rc.10475
facman-0.1.0+release.10483
facman-0.1.1+hotfix.10495
```

Artifact filenames may normalize `+` to `-` when a package manager requires it,
but the canonical version remains in the build manifest.

## Component Versions

Every release records:

```text
facman_product_version
factorio_binding_version
flb_abi_version
universal_launcher_version
ulk_abi_version
ulu_abi_version
universal_setup_version
usk_abi_version
usu_abi_version
command_contract_version
result_contract_version
refusal_contract_version
schema_versions
package_revision
```

The current contract files are:

- `release/index/build_manifest.v1.toml`
- `release/index/dependency_lock.v1.toml`

## Schema Versions

Schema versions are not tied to product SemVer. A product release can ship a new
package revision without changing a schema version, and a schema migration can
be explicit without changing every binary ABI.

## ABI Versions

Public ABI versions must be declared. Any ABI mismatch must refuse loudly before
runtime mutation or launch execution.
