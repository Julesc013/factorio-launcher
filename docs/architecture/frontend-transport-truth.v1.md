# Frontend transport truth v1

Desktop compatibility frontends invoke the native `facman` process. They do not
implement JSON-RPC and their transport classes are named `CliProcessClient`.

WinForms launches commands asynchronously, uses `ProcessStartInfo.ArgumentList`
when the running framework exposes it, drains stdout and stderr concurrently,
supports cancellation and a 30-second timeout, terminates timed-out children,
and decodes structured refusal or error objects. UI event handlers await command
completion and do not synchronously block the Windows message loop.

AppKit drains both pipes on independent utility queues, observes termination via
the task termination handler, enforces a bounded timeout, and reports results on
the main queue. It does not call `waitUntilExit`. AppKit remains compile-only:
no `.app` runtime or publication claim is made until a real bundle is executed.

The TUI and daemon sources remain as non-product experiments. Their CMake
targets exist only with `FACMAN_BUILD_EXPERIMENTAL_FRONTENDS=ON`, which defaults
to `OFF`. Product GUI profiles no longer include these scaffold entrypoints.
The portable TUI profile is explicitly unpublished and requires the opt-in flag.

`tools/frontend_transport_truth_check.py` enforces these naming, process,
asynchrony, option, and package-claim boundaries in the strict validation lane.
