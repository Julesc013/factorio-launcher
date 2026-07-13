# Factorio Daemon Placeholder

`apps/daemon/` reserves the future daemon/job-runner ownership boundary. The
current executable is an explicit unavailable placeholder: it does not host an
IPC protocol, supervise jobs, accept remote clients, or support publication.

The daemon becomes a product capability only after its versioned protocol,
authentication/authorization boundary, cancellation, recovery, lifecycle, and
package runtime receive their own reviewed proof. CLI and GUI packages must not
advertise this placeholder as a working transport.
