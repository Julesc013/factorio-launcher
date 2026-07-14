# Factorio portable setup binding v1

Status: implemented for `M1-WU9` as a read-only product binding and Universal
Setup gateway. Managed setup apply remains unavailable.

## Ownership boundary

FacMan owns the Factorio recipe and the interpretation of Factorio-specific
layout and capability markers. Universal Setup owns stable archive inspection
and, in later work units, generic setup planning and lifecycle mutation.
Universal Launcher owns only product-neutral setup-result and install-reference
handoff contracts.

No Factorio path, Steam identifier, expansion name, or execution rule is added
to either Universal repository by this binding.

## Accepted source

The v1 recipe accepts an operator-supplied local ZIP archive for a portable
Windows target. It binds the exact archive SHA-256 at plan time and permits a
flat application root or one selected top-level prefix. It requires:

- `bin/x64/factorio.exe`;
- `data/base/info.json`.

`data/space-age/info.json` is an optional locally observable capability marker.
Its presence does not prove licensing, publisher authenticity, or execution
readiness. Product version remains subject to a post-stage structural JSON
probe; the executable is never launched by archive inspection.

The recipe refuses embedded user or foreign state, including saves, mods,
configuration, script output, scenarios, and temporary content. Universal
Setup independently rejects unsafe ZIP structure, path traversal, collisions,
links, unstable source identity, and configured resource-budget violations.

## Gateway result

`SetupGateway::inspect_install_archive` sends the archive to the public
`install_local.inspect` command and accepts only its typed successful
`usk.archive_inspection.v1` payload. The Factorio layer then produces a
`facman.factorio.archive_assessment.v1` projection that binds:

- recipe and archive digests;
- deterministic inspected entry-set digest;
- selected application-root prefix and strip policy;
- file, directory, and uncompressed-byte totals;
- Factorio entrypoint and locally observed content capabilities;
- `candidate_unproven_until_live_h1` strict-isolation classification;
- `publisher_authenticity_proven = false`;
- `mutation_executed = false`.

Malformed provider envelopes are refused. A provider success cannot be
converted into a Factorio layout success unless every recipe invariant also
passes.

## Authority exclusions

This work unit does not extract the archive, construct an authoritative setup
plan, create a target, write installed state, register an install reference, or
enable any apply command. It grants no network, credential, registry,
elevation, package-manager, vendor-installer, Steam-mutation, or Factorio
execution authority.

H1 remains a separate human-reviewed gate. The recorded Steam-backed verdict
remains `Fail`, and standalone/manual isolation remains `unproven`.

## Proof

The native recipe smoke covers canonical recipe loading, digest binding,
required and forbidden paths, flat and single-prefix layouts, capability
classification, ambiguity, collisions, foreign roots, and invalid versions.
The gateway smoke creates a synthetic classic ZIP, routes it through Universal
Setup inspection, and verifies the Factorio assessment without creating an
installation target. Python policy checks keep the generated recipe projection,
schema, provider pins, setup routing, and authority boundaries current.
