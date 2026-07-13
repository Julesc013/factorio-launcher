# Command Client

Frontend-neutral client seam for invoking the command graph through CLI JSON or
direct C ABI without making one frontend depend on another. Daemon JSON-RPC is
represented only by an explicitly unavailable future transport boundary.

The CMake graph is intentionally split:

- `facman_client_model_static` owns request/result decoding and the facade model;
- `facman_transport_direct_static` alone embeds and links FLB;
- `facman_transport_process_static` owns child-process adapters without FLB;
- `facman_transport_daemon_static` is the unavailable IPC placeholder;
- `facman_workspace_resolver_static` owns host workspace selection;
- `facman_client_static` is the compatibility facade that selects all current transports.

Consumers that need only process transport can link `facman::transport_process`
without inheriting the Factorio binding or application runtime.
