# Provider package-manifest import

`tools/provider_package_manifest_import.py` is the only supported path from a
reviewed installed-provider package set to FacMan's tracked provider identity.
It does not discover or predict a provider revision.

## Inputs

An import requires all six Release/x86_64 package profiles (Linux, macOS and
Windows; static and shared), their package roots, a reviewed policy, an exact
local provider source checkout, the protected ref, the FacMan release-context
commit, and `release/index`.

The policy is executable authority, not caller-supplied metadata. It must be a
regular, non-link file below
`release/policies/provider-package-import/<provider-id>.v1.json`, and its
filtered Git blob must be owned by the exact `--facman-revision`. An arbitrary
external `--policy` file is refused. The requested protected ref must exactly
match the stable ref in that owned policy.

The reviewed policy binds:

- the provider repository and `refs/heads/main`;
- package, ABI and state/journal format versions;
- the ABI manifest, full contract inventory, selected FacMan contract set,
  public-header inventory, and per-profile artifact inventories;
- exact configuration, architecture, licence, and installed targets.

The provider source commit must be the exact protected-ref tip, not merely a
reachable task or development commit. The manifest tree must match Git.

## Generated tracked surfaces

After all package bytes and current tracked inputs pass coherence checks, the
importer projects these files together:

- `workspace_lock.v1.toml`;
- `dependency_lock.v1.toml`;
- `providers.lock.v2.toml`, including the release compiler's six SDK profiles;
- `build_manifest.v1.toml`;
- `sbom.components.v1.json`.

The CMake exact package version is the generated `cmake_package_version` in the
provider record. `cmake/FacManProviders.cmake` reads it from the lock and has no
provider package-number literal.

## Operation

Use `--apply` once to stage all five tracked projections, retain exact original
backups and digests, and write a durable recovery journal before the first
replacement. Each completed replacement advances that journal. An ordinary
failure rolls every file back; an abrupt interruption leaves the bounded
`.provider-package-import-transaction.v1` directory and blocks check/apply
until explicit `--recover` restores and verifies all original bytes. The
journal conforms to
`facman.provider_package_import_transaction.v1`. Use the same inputs with
`--check` in validation and CI; it refuses any byte difference. Pass
`--evidence` to write a non-authorizing digest receipt conforming to
`facman.provider_package_import.v1`.

Only the imported provider's six package rows receive the new FacMan evidence
revision. Other provider rows retain their own provenance; an import never
relabels historical evidence. State/journal format evidence is projected from
the accepted manifest matrix after policy comparison, rather than copied from
the policy object.

The command intentionally refuses stale or mixed current projections, an
incomplete or duplicate profile matrix, changed/unrecorded package artifacts,
wrong ref/commit/tree, wrong ABI or state format, contract/header drift,
profile drift, and changed manifest bytes.

Do not run `--apply` for a provider task head. Build the packages and manifests
from the actual protected-main merge first.
