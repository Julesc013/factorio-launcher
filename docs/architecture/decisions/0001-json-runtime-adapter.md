# ADR 0001: JSON Runtime Adapter

Status: accepted for R3.4.

## Decision

FacMan admits PicoJSON at commit
`111c9be5188f7350c2eac9ddaedd8cca3d7bf394` as its one source-only JSON
dependency. PicoJSON is BSD-2-Clause licensed, header-only, has no runtime
network behavior, and has no transitive runtime dependencies.

First-party code consumes it only through `runtime/core/json/fl_json.h`.
Domain code must not include `picojson.h`, scan serialized JSON text, or expose
PicoJSON types in public/product APIs. The adapter applies byte, nesting, node,
and string budgets and rejects duplicate object keys before accepting the
upstream parse result.

## Provenance

- source file SHA-256:
  `eecfb89d1a72ab38a20322e4f959210c432167350fc84956856d94dfe6e4a526`;
- license file SHA-256:
  `325af23f1286ed778387551ac1d9dfb6a6f5427861393278793e97c3a07ccbeb`;
- full notice: `external/picojson/LICENSE`;
- dependency lock: `release/index/dependency_lock.v1.toml`;
- SBOM seed: `release/index/sbom.components.v1.json`.

## Consequences

The wrapper is the compatibility and policy boundary. PicoJSON can be replaced
without changing domain APIs. Runtime code remains C++17 and does not require a
package manager, opaque binary, or network access.
