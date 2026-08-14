// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace FacMan.WinForms
{
    public sealed class CliProcessClient
    {
        private readonly TransportOptions options;
        private readonly Func<TransportIdentity> identityFactory;
#if FACMAN_TRANSPORT_HARNESS
        private readonly Func<string, PackagedBackendIdentity> backendIdentityFactory;
        private readonly bool requirePackagedBackendIdentity;
#endif

        public CliProcessClient()
            : this(new TransportOptions())
        {
        }

        public CliProcessClient(TransportOptions options)
        {
            if (options == null) throw new ArgumentNullException("options");
            this.options = options;
            identityFactory = TransportIdentity.Create;
#if FACMAN_TRANSPORT_HARNESS
            backendIdentityFactory = delegate { return PackagedBackendIdentity.OpenProduction(); };
            requirePackagedBackendIdentity = true;
#endif
        }

#if FACMAN_TRANSPORT_HARNESS
        internal CliProcessClient(
            TransportOptions options,
            Func<TransportIdentity> identityFactory)
        {
            if (options == null) throw new ArgumentNullException("options");
            if (identityFactory == null) throw new ArgumentNullException("identityFactory");
            this.options = options;
            this.identityFactory = identityFactory;
            backendIdentityFactory = PackagedBackendIdentity.OpenUntrustedTransportTest;
            requirePackagedBackendIdentity = false;
        }
#endif

        public async Task<CommandResult> InvokeAsync(
            CommandDefinition command,
            IDictionary<string, object> payload,
            string workspace,
            string configuredCliPath,
            CancellationToken cancellationToken)
        {
            return await InvokeAsync(
                command,
                payload,
                workspace,
                configuredCliPath,
                command == null ? false : command.DryRunDefault,
                identityFactory(),
                cancellationToken).ConfigureAwait(false);
        }

        internal async Task<CommandResult> InvokeAsync(
            CommandDefinition command,
            IDictionary<string, object> payload,
            string workspace,
            string configuredCliPath,
            bool dryRun,
            TransportIdentity identity,
            CancellationToken cancellationToken)
        {
            if (command == null) throw new ArgumentNullException("command");
            if (identity == null) throw new ArgumentNullException("identity");
            if (dryRun != command.DryRunDefault &&
                !String.Equals(command.BackendId, "presentation.action", StringComparison.Ordinal))
                return LocalRefusal(
                    command,
                    identity,
                    "frontend_effect_override_forbidden",
                    "Only the typed presentation action seam can strengthen effect admission.");
            if (cancellationToken.IsCancellationRequested)
                return CommandResult.CancelledBeforeDispatch(
                    command.Id,
                    command.BackendId,
                    identity.OperationId,
                    identity.AttemptId,
                    "The backend command was cancelled before dispatch.");

            PackagedBackendIdentity backend;
            try
            {
#if FACMAN_TRANSPORT_HARNESS
                // configuredCliPath is accepted for source compatibility only.
                backend = backendIdentityFactory(configuredCliPath);
#else
                // configuredCliPath is accepted for source compatibility only.
                // Ordinary builds have no executable-path injection seam.
                backend = PackagedBackendIdentity.OpenProduction();
#endif
            }
            catch (Exception ex)
            {
                return LocalRefusal(
                    command,
                    identity,
                    "frontend_backend_identity_unavailable",
                    "The packaged backend identity could not be established: " + ex.Message);
            }

            using (backend)
            {
                DateTime deadline = DateTime.UtcNow + options.OperationTimeout;
#if FACMAN_TRANSPORT_HARNESS
                if (requirePackagedBackendIdentity)
#endif
                {
                    CommandDefinition inspect = GeneratedCommandCatalog.Find("product.inspect");
                    bool callerIsInspect =
                        String.Equals(command.BackendId, inspect.BackendId, StringComparison.Ordinal);
                    TransportIdentity inspectIdentity = callerIsInspect ? identity : identityFactory();
                    CommandResult inspection = await InvokeCoreAsync(
                        inspect,
                        callerIsInspect ? payload : new Dictionary<string, object>(),
                        workspace,
                        inspectIdentity,
                        backend,
                        inspect.DryRunDefault,
                        deadline,
                        cancellationToken).ConfigureAwait(false);
                    if (cancellationToken.IsCancellationRequested &&
                        inspection.OperationOutcome == "cancelled_before_dispatch")
                        return CommandResult.CancelledBeforeDispatch(
                            command.Id,
                            command.BackendId,
                            identity.OperationId,
                            identity.AttemptId,
                            "The backend command was cancelled before dispatch.");
                    try
                    {
                        backend.ValidateHandshake(inspection);
                    }
                    catch (Exception ex)
                    {
                        return LocalRefusal(
                            command,
                            identity,
                            "frontend_backend_identity_unavailable",
                            "The packaged backend identity preflight failed: " + ex.Message);
                    }
                    if (callerIsInspect) return inspection;
                    if (String.Equals(command.BackendId, "run.execute", StringComparison.Ordinal))
                    {
                        CommandDefinition runRoute = GeneratedCommandCatalog.Find("run.execute");
                        if (runRoute.Status != CommandStatus.Implemented ||
                            !String.Equals(
                                runRoute.Availability, "available", StringComparison.Ordinal))
                            return LocalRefusal(
                                command,
                                identity,
                                "frontend_backend_identity_unavailable",
                                "The verified backend identity does not enable run.execute: " +
                                runRoute.DeferredReason);
                    }
                    if (DateTime.UtcNow >= deadline - options.CleanupReserve)
                        return LocalRefusal(
                            command,
                            identity,
                            "frontend_backend_identity_unavailable",
                            "The packaged backend identity preflight exhausted the dispatch budget.");
                }

                return await InvokeCoreAsync(
                    command,
                    payload,
                    workspace,
                    identity,
                    backend,
                    dryRun,
                    deadline,
                    cancellationToken).ConfigureAwait(false);
            }
        }

        private async Task<CommandResult> InvokeCoreAsync(
            CommandDefinition command,
            IDictionary<string, object> payload,
            string workspace,
            TransportIdentity identity,
            PackagedBackendIdentity backend,
            bool dryRun,
            DateTime deadline,
            CancellationToken cancellationToken)
        {
            if (cancellationToken.IsCancellationRequested)
                return CommandResult.CancelledBeforeDispatch(
                    command.Id,
                    command.BackendId,
                    identity.OperationId,
                    identity.AttemptId,
                    "The backend command was cancelled before dispatch.");

            byte[] request;
            try
            {
                request = TransportRequestEncoder.Encode(
                    command, payload, workspace, identity, dryRun);
            }
            catch (Exception ex)
            {
                return LocalRefusal(
                    command,
                    identity,
                    "frontend_backend_request_invalid",
                    "The transport request could not be serialized: " + ex.Message);
            }
            if (request.Length > options.MaximumRequestBytes)
                return LocalRefusal(
                    command,
                    identity,
                    "frontend_backend_request_too_large",
                    "The transport request exceeds the exact raw-byte budget of " +
                    options.MaximumRequestBytes.ToString() + " bytes.");

            string executable = backend.ExecutablePath;
            if (String.IsNullOrWhiteSpace(executable))
                return LocalRefusal(
                    command,
                    identity,
                    "frontend_backend_unavailable",
                    "No package-bound facman CLI executable is available.");

            DateTime dispatchDeadline = deadline - options.CleanupReserve;
            TransportDispatchState state = TransportDispatchState.NotStarted;
            WindowsContainedProcess process = null;
            BoundedByteChannel stdout = null;
            BoundedByteChannel stderr = null;
            try
            {
                process = WindowsContainedProcess.StartSuspended(
                    executable,
                    "rpc --stdio",
                    backend.RevalidateImmediatelyBeforeProcessCreation,
                    backend.ValidateCreatedSuspendedProcess);
                state = TransportDispatchState.ProcessStartedRequestNotWritten;
                stdout = BoundedByteChannel.Start(
                    process.StandardOutput, options.MaximumStdoutBytes);
                stderr = BoundedByteChannel.Start(
                    process.StandardError, options.MaximumStderrBytes);

                if (cancellationToken.IsCancellationRequested)
                    return await TerminateBeforeDispatchAsync(
                        process, stdout, stderr, command, identity, deadline, true)
                        .ConfigureAwait(false);
                if (DateTime.UtcNow >= dispatchDeadline)
                    return await TerminateBeforeDispatchAsync(
                        process, stdout, stderr, command, identity, deadline, false)
                        .ConfigureAwait(false);

                process.Resume();
                state = TransportDispatchState.RequestWriteStartedDispatchUncertain;
                using (CancellationTokenSource writeCancellation =
                    CancellationTokenSource.CreateLinkedTokenSource(cancellationToken))
                {
                    writeCancellation.CancelAfter(Remaining(dispatchDeadline));
                    Task write = process.StandardInput.WriteAsync(
                        request, 0, request.Length, writeCancellation.Token);
                    Task writeCancellationSignal = Task.Delay(
                        Timeout.Infinite, writeCancellation.Token);
                    Task first = await Task.WhenAny(
                        write,
                        writeCancellationSignal,
                        stdout.LimitExceeded,
                        stderr.LimitExceeded,
                        process.ExitTask).ConfigureAwait(false);
                    if (first != write)
                    {
                        writeCancellation.Cancel();
                        string code = first == stdout.LimitExceeded || first == stderr.LimitExceeded
                            ? "frontend_backend_output_exhausted"
                            : "frontend_backend_early_exit";
                        return await TerminateUnknownAsync(
                            process,
                            stdout,
                            stderr,
                            command,
                            identity,
                            deadline,
                            code,
                            "The backend transport failed after request dispatch became possible.")
                            .ConfigureAwait(false);
                    }
                    try
                    {
                        await write.ConfigureAwait(false);
                    }
                    catch (Exception ex)
                    {
                        return await TerminateUnknownAsync(
                            process,
                            stdout,
                            stderr,
                            command,
                            identity,
                            deadline,
                            cancellationToken.IsCancellationRequested
                                ? "frontend_backend_cancelled"
                                : "frontend_backend_write_failed",
                            "The request write did not complete after dispatch became possible: " +
                            ex.Message).ConfigureAwait(false);
                    }
                }
                process.CloseInput();
                state = TransportDispatchState.RequestWrittenResponsePending;
                return await AwaitTerminalAsync(
                    process,
                    stdout,
                    stderr,
                    command,
                    identity,
                    dispatchDeadline,
                    deadline,
                    cancellationToken).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                if (state < TransportDispatchState.RequestWriteStartedDispatchUncertain)
                {
                    if (process != null)
                        await CleanupProcessAsync(process, stdout, stderr, deadline)
                            .ConfigureAwait(false);
                    return LocalRefusal(
                        command,
                        identity,
                        "frontend_backend_start_failed",
                        "The contained backend could not start before dispatch: " + ex.Message);
                }
                if (process != null && stdout != null && stderr != null)
                    return await TerminateUnknownAsync(
                        process,
                        stdout,
                        stderr,
                        command,
                        identity,
                        deadline,
                        "frontend_backend_error",
                        "The backend transport failed after dispatch became possible: " + ex.Message)
                        .ConfigureAwait(false);
                return CommandResult.OutcomeUnknown(
                    command.Id,
                    command.BackendId,
                    identity.OperationId,
                    identity.AttemptId,
                    "frontend_backend_error",
                    "The backend transport failed after dispatch became possible: " + ex.Message,
                    String.Empty,
                    String.Empty);
            }
            finally
            {
                if (process != null) process.Dispose();
            }
        }

        private async Task<CommandResult> AwaitTerminalAsync(
            WindowsContainedProcess process,
            BoundedByteChannel stdout,
            BoundedByteChannel stderr,
            CommandDefinition command,
            TransportIdentity identity,
            DateTime dispatchDeadline,
            DateTime deadline,
            CancellationToken cancellationToken)
        {
            Task cancellation = Task.Delay(Timeout.Infinite, cancellationToken);
            Task timeout = Task.Delay(Remaining(dispatchDeadline));
            Task all = Task.WhenAll(
                new Task[] { process.ExitTask, stdout.Completion, stderr.Completion });
            bool rootHandled = false;
            while (true)
            {
                Task rootExit = rootHandled ? Never() : process.ExitTask;
                Task completed = await Task.WhenAny(
                    all,
                    rootExit,
                    cancellation,
                    timeout,
                    stdout.LimitExceeded,
                    stderr.LimitExceeded).ConfigureAwait(false);
                if (completed == all)
                    return DecodeCompleted(
                        process, stdout, stderr, command, identity, false);
                if (completed == rootExit)
                {
                    await ObserveRootExitAsync(process).ConfigureAwait(false);
                    rootHandled = true;
                    continue;
                }
                if (completed == cancellation)
                {
                    CommandResult raced = await TryCancellationCompletionAsync(
                        process,
                        stdout,
                        stderr,
                        command,
                        identity,
                        rootHandled,
                        dispatchDeadline).ConfigureAwait(false);
                    if (raced != null) return raced;
                    return await TerminateUnknownAsync(
                        process,
                        stdout,
                        stderr,
                        command,
                        identity,
                        deadline,
                        "frontend_backend_cancelled",
                        "Cancellation was requested after dispatch; backend effects are unknown.")
                        .ConfigureAwait(false);
                }
                if (completed == timeout)
                    return await TerminateUnknownAsync(
                        process,
                        stdout,
                        stderr,
                        command,
                        identity,
                        deadline,
                        "frontend_backend_timeout",
                        "The whole-operation deadline expired after dispatch; backend effects are unknown.")
                        .ConfigureAwait(false);
                return await TerminateUnknownAsync(
                    process,
                    stdout,
                    stderr,
                    command,
                    identity,
                    deadline,
                    "frontend_backend_output_exhausted",
                    "A backend output channel exceeded its exact raw-byte budget after dispatch.")
                    .ConfigureAwait(false);
            }
        }

        private async Task<CommandResult> TryCancellationCompletionAsync(
            WindowsContainedProcess process,
            BoundedByteChannel stdout,
            BoundedByteChannel stderr,
            CommandDefinition command,
            TransportIdentity identity,
            bool rootHandled,
            DateTime dispatchDeadline)
        {
            DateTime graceDeadline = DateTime.UtcNow + options.CancellationCompletionGrace;
            if (graceDeadline > dispatchDeadline) graceDeadline = dispatchDeadline;
            Task all = Task.WhenAll(
                new Task[] { process.ExitTask, stdout.Completion, stderr.Completion });
            while (DateTime.UtcNow < graceDeadline)
            {
                Task rootExit = rootHandled ? Never() : process.ExitTask;
                Task completed = await Task.WhenAny(
                    all,
                    rootExit,
                    stdout.LimitExceeded,
                    stderr.LimitExceeded,
                    Task.Delay(Remaining(graceDeadline))).ConfigureAwait(false);
                if (completed == all)
                {
                    CommandResult result = DecodeCompleted(
                        process, stdout, stderr, command, identity, false);
                    return result.OperationOutcome == "completed"
                        ? result.CancellationRequestedButCompleted()
                        : result;
                }
                if (completed == rootExit)
                {
                    await ObserveRootExitAsync(process).ConfigureAwait(false);
                    rootHandled = true;
                    continue;
                }
                return null;
            }
            return null;
        }

        private CommandResult DecodeCompleted(
            WindowsContainedProcess process,
            BoundedByteChannel stdout,
            BoundedByteChannel stderr,
            CommandDefinition command,
            TransportIdentity identity,
            bool cancellationObserved)
        {
            BoundedByteReadResult output = stdout.Completion.GetAwaiter().GetResult();
            BoundedByteReadResult error = stderr.Completion.GetAwaiter().GetResult();
            if (output.Exceeded || error.Exceeded)
                throw new InvalidDataException("A backend output channel exceeded its raw-byte budget.");
            if (output.Error != null) throw new InvalidDataException("Backend stdout read failed.", output.Error);
            if (error.Error != null) throw new InvalidDataException("Backend stderr read failed.", error.Error);
            int exitCode = process.ExitTask.GetAwaiter().GetResult();
            CommandResult result = TransportResponseDecoder.Decode(
                command,
                exitCode,
                output.Bytes,
                error.Bytes,
                identity,
                options.MaximumStdoutBytes);
            return cancellationObserved && result.OperationOutcome == "completed"
                ? result.CancellationRequestedButCompleted()
                : result;
        }

        private async Task<CommandResult> TerminateBeforeDispatchAsync(
            WindowsContainedProcess process,
            BoundedByteChannel stdout,
            BoundedByteChannel stderr,
            CommandDefinition command,
            TransportIdentity identity,
            DateTime deadline,
            bool cancelled)
        {
            await CleanupProcessAsync(process, stdout, stderr, deadline).ConfigureAwait(false);
            if (cancelled)
                return CommandResult.CancelledBeforeDispatch(
                    command.Id,
                    command.BackendId,
                    identity.OperationId,
                    identity.AttemptId,
                    "The backend command was cancelled before dispatch.");
            return LocalRefusal(
                command,
                identity,
                "frontend_backend_timeout_before_dispatch",
                "The operation deadline expired before request dispatch.");
        }

        private async Task<CommandResult> TerminateUnknownAsync(
            WindowsContainedProcess process,
            BoundedByteChannel stdout,
            BoundedByteChannel stderr,
            CommandDefinition command,
            TransportIdentity identity,
            DateTime deadline,
            string code,
            string reason)
        {
            bool containment = await CleanupProcessAsync(
                process, stdout, stderr, deadline).ConfigureAwait(false);
            BoundedByteReadResult output = CompletedResult(stdout);
            BoundedByteReadResult error = CompletedResult(stderr);
            string stdoutText = output == null
                ? String.Empty
                : TransportResponseDecoder.DecodeDiagnostic(output.Bytes);
            string stderrText = error == null
                ? String.Empty
                : TransportResponseDecoder.DecodeDiagnostic(error.Bytes);
            if (!containment)
                reason += " Complete process-tree containment could not be proved before the deadline.";
            return CommandResult.OutcomeUnknown(
                command.Id,
                command.BackendId,
                identity.OperationId,
                identity.AttemptId,
                code,
                reason + " Run workspace.recovery.inspect before retrying.",
                stdoutText,
                stderrText);
        }

        private static async Task<bool> CleanupProcessAsync(
            WindowsContainedProcess process,
            BoundedByteChannel stdout,
            BoundedByteChannel stderr,
            DateTime deadline)
        {
            process.CloseInput();
            bool terminationRequested = process.TerminateTree();
            Task<bool> tree = process.WaitForTreeEmptyAsync(deadline);
            List<Task> completion = new List<Task>();
            completion.Add(Suppress(process.ExitTask));
            if (stdout != null) completion.Add(stdout.Completion);
            if (stderr != null) completion.Add(stderr.Completion);
            Task all = Task.WhenAll(completion.ToArray());
            Task winner = await Task.WhenAny(all, Task.Delay(Remaining(deadline)))
                .ConfigureAwait(false);
            bool treeEmpty = await tree.ConfigureAwait(false);
            return terminationRequested && treeEmpty && winner == all;
        }

        private static async Task ObserveRootExitAsync(WindowsContainedProcess process)
        {
            await Suppress(process.ExitTask).ConfigureAwait(false);
            process.TerminateTree();
        }

        private static BoundedByteReadResult CompletedResult(BoundedByteChannel channel)
        {
            return channel != null && channel.Completion.Status == TaskStatus.RanToCompletion
                ? channel.Completion.Result
                : null;
        }

        private static Task Suppress(Task task)
        {
            return task.ContinueWith(
                delegate { },
                CancellationToken.None,
                TaskContinuationOptions.ExecuteSynchronously,
                TaskScheduler.Default);
        }

        private static Task Never()
        {
            return new TaskCompletionSource<bool>().Task;
        }

        private static int Remaining(DateTime deadline)
        {
            double milliseconds = (deadline - DateTime.UtcNow).TotalMilliseconds;
            if (milliseconds <= 0) return 0;
            return milliseconds >= Int32.MaxValue ? Int32.MaxValue : (int)Math.Ceiling(milliseconds);
        }

        private static CommandResult LocalRefusal(
            CommandDefinition command,
            TransportIdentity identity,
            string code,
            string reason)
        {
            return CommandResult.LocalRefusal(
                command.Id,
                command.BackendId,
                code,
                reason,
                identity.OperationId,
                identity.AttemptId);
        }

    }
}
