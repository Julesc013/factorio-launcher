# Integration Tests

Cross-module tests for discovery, launch-plan generation, workspace behavior,
and export/import flows.

## Real low-space backup regression

`facman_world_backup_low_space.py` checks an explicit extracted Linux CLI
package against real filesystem exhaustion. It creates separate 4 MiB tmpfs
volumes for the owned test workspace and backup destination in a private
mount namespace. It preserves a valid backup, fills only the destination,
checks the typed refusal and absence of partial output, then restores capacity
and retries the identical target. Package and public fixture inventories must
remain unchanged. Normal completion unmounts both volumes; the supervisor
owns the worker process group and a 240-second deadline.

Use a Linux host with mount namespaces and tmpfs available. Root execution or
already available noninteractive sudo is required. The caller admits the
package's source, archive, provenance and digest and supplies a new receipt
filename beneath an existing marker-owned task evidence directory, outside
the source and extracted package. Preserve each previous attempt and its logs.

    PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 python3 -B \
      tests/integration/facman_world_backup_low_space.py \
      --executable "$FACMAN_CLI_EXE" --package-root "$FACMAN_PACKAGE_ROOT" \
      --source-root "$PWD" \
      --evidence "$FACMAN_TASK_EVIDENCE/world-backup-low-space.json"

The receipt retains the executable digest, host and namespace identities,
actual capacity and kernel ENOSPC result, refusal, preservation oracles,
same-target retry and cleanup. Native stdout/stderr and the supervisor log
stay beside the receipt. A timeout may leave only the supervisor log;
inspect that attempt before starting another one.

This manual package regression requires privileges beyond the ordinary unit
suite. A WSL result remains evidence for the supplied package on WSL. The
caller must retain exact package/source custody and final product-family,
supported-host, game and human qualification separately.
