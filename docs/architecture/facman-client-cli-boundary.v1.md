# FacMan client and CLI boundary v1

## Decision

The native CLI is a frontend over `facman::client::FacManClient`. It may parse
arguments, normalize aliases, construct command payloads, render responses, and
map command status to an exit code. Backend behavior belongs to the Factorio
application handlers reached through the public FLB command bridge.

The enforced dependency direction is:

```text
facman_cli -> facman_client_static -> FLB command bridge -> application handlers
```

`facman_cli` links only `facman_client_static`. The CLI does not include or link
workspace persistence, archive, transaction, diagnostics, discovery, modset,
launch, runtime-package, Universal Setup, or Universal Launcher backend APIs.
Response-envelope decoding and JSON member access are owned by the client.

## Client API and transport truth

`runtime/client/facman_client.h` defines the stable request, response, client,
and transport interfaces.

- `DirectFlbTransport` is the working in-process transport. It creates an FLB
  context for the selected workspace and executes the canonical command through
  the C ABI command client.
- `CliProcessTransport` is a compatibility declaration only. It returns
  `cli_process_transport_unavailable` because invoking the CLI from its own
  backend would be recursive and misleading.
- `DaemonTransport` is an explicit unavailable interface. It returns
  `daemon_transport_unavailable` until a real daemon protocol is implemented.

Transport names describe implemented behavior; none claim JSON-RPC.

## Canonical grouped routes

The provider command registry has a fixed capacity of 32 and is now full.
Frontend aliases whose behavior is related are normalized into two typed
application routes:

- `setup.operation` owns setup-backed package and managed-install operations.
- `utility.operation` owns bounded server, Mod Portal, developer, and diagnostic
  utility operations.

The public aliases remain the compatibility surface. The grouped runtime IDs
are internal catalog entries and are not emitted as CLI help or completions.
Adding another registered runtime command requires an explicit provider-registry
capacity change; it must not silently displace an existing command.

## Optional Universal Setup

`FACMAN_WITH_SETUP` defaults to `ON`.

- With setup enabled, the application links Universal Setup and the package
  runtime only at the application boundary.
- With setup disabled, Universal Setup is not configured or linked. Safe
  read-only commands remain functional and setup operations return the
  structured `setup_unavailable` refusal.

The CLI has the same dependency graph in both configurations.

## Mechanical enforcement

`tools/client_cli_boundary_check.py` fails when the CLI regains backend tokens,
legacy backend sources, direct backend link dependencies, or loses the client
and optional-setup boundaries. The existing apps-boundary and target-dependency
fitness checks now carry zero CLI exceptions.

Native proof covers response decoding and all declared transport states in
`facman_client_smoke`. CLI characterization tests preserve aliases, JSON output,
refusal output, and exit status. Both setup-enabled and setup-disabled native
builds are required proof for this boundary.
