# FacMan client and CLI boundary v1

## Decision

The native CLI is a frontend over `facman::client::FacManClient`. It may parse
arguments, normalize aliases, construct command payloads, render responses, and
map command status to an exit code. Backend behavior belongs to the Factorio
application handlers reached through the public FLB command bridge.

The compatibility-facade dependency direction is:

```text
facman_cli -> facman_client_static -> FLB command bridge -> application handlers
```

The implementation target graph is narrower:

```text
facman_client_model_static
  request/result model, decoding, facade, cancellation, progress

facman_transport_direct_static
  -> client model + FLB

facman_transport_process_static
  -> client model + process/platform adapters

facman_transport_daemon_static
  -> client model only; unavailable

facman_client_static
  -> compatibility facade selecting all current transports
```

`facman_cli` links only `facman_client_static`. The CLI does not include or link
workspace persistence, archive, transaction, diagnostics, discovery, modset,
launch, runtime-package, Universal Setup, or Universal Launcher backend APIs.
Response-envelope decoding and JSON member access are owned by the client.

## Client API and transport truth

`runtime/client/facman_client_model.h` defines the request, response, client,
and abstract transport interfaces. Transport-specific headers no longer force a
process-only consumer to compile against or link the embedded Factorio backend.
`runtime/client/facman_client.h` remains a source-compatible umbrella.

- `DirectFlbTransport` is the working in-process transport. It creates one FLB
  context for the selected workspace, registers the graph once, serializes
  calls on that context, reuses it for the transport lifetime, and destroys it
  once. Responses retain a parsed payload document so repeated accessors do not
  reparse the same JSON.
- `CliProcessTransport` is a working compatibility transport for external
  clients. It invokes `facman rpc --stdio` with one bounded transport envelope,
  concurrently drains bounded stdout and stderr, and accepts only the machine
  response document on stdout. It is not used recursively by the CLI itself.
  Windows assigns the suspended child to a kill-on-close Job Object before it
  runs; POSIX places it in a dedicated process group. Cancellation, timeout, or
  output overflow terminates that whole child tree.
- `DaemonTransport` is an explicit unavailable interface. It returns
  `daemon_transport_unavailable` until a real daemon protocol is implemented.

Transport names describe implemented behavior; none claim JSON-RPC.

`CommandRequest` also carries optional cooperative execution controls without
changing the public C ABI. `CancellationToken` is thread-safe and is checked
before transport selection, before direct dispatch after lock acquisition, and
after the C ABI call. `ProgressSink` receives bounded stage updates for waiting,
dispatch, response decoding, and completion. A positive timeout is mandatory;
process transports additionally enforce it against the child process. Direct
FLB execution remains synchronous, so cancellation requested during a native
call is observed at the first safe boundary after that call returns.

## Canonical grouped routes

The provider command registry uses allocator-backed geometric growth under an
explicit storage budget; the former fixed capacity of 32 is removed.
Every setup, package, Mod Portal, server, diagnostic, and developer operation
has a first-class runtime command. Hyphenated CLI spellings such as
`install-version`, `bug-report`, and `dump-data` normalize to canonical IDs such
as `installs.install_version`, `dev.bug_report`, and `dev.dump_data` before the
FLB call. `setup.operation` and `utility.operation` are not registered and are
not emitted in help, completions, frontend metadata, or the executable command
graph.

The application decoder retains internal normalization code for compatibility
corpus coverage, but the public FLB bridge no longer bypasses the registered
command graph. Direct calls to those unregistered IDs now return the ordinary
`unsupported_command` result. Older clients must migrate to first-class routes.

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
