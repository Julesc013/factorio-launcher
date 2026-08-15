// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

internal static class IdentityHarness
{
    private static int Main(string[] args)
    {
        if (args.Length != 2)
        {
            Console.Error.WriteLine(
                "usage: FacMan.BackendIdentity.Harness <frontend-assembly> <package-root>");
            return 2;
        }
        string temporaryRoot = Path.Combine(
            Path.GetTempPath(), "facman-backend-identity-" + Guid.NewGuid().ToString("N"));
        string junctionPath = null;
        try
        {
            string sourcePackage = Path.GetFullPath(args[1]);
            string universalLauncherRevision = PackageRevision(
                sourcePackage, "universal_launcher_revision");
            Assembly frontend = Assembly.LoadFrom(Path.GetFullPath(args[0]));
            Type identityType = frontend.GetType(
                "FacMan.WinForms.PackagedBackendIdentity", true);
            Type clientType = frontend.GetType("FacMan.WinForms.CliProcessClient", true);
            Type processType = frontend.GetType("FacMan.WinForms.WindowsContainedProcess", true);
            Type commandResultType = frontend.GetType("FacMan.WinForms.CommandResult", true);
            Require(
                identityType.GetMethod(
                    "OpenUntrustedTransportTest",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static) == null,
                "the ordinary Release assembly contains the untrusted backend override");
            Require(
                clientType.GetField(
                    "backendIdentityFactory",
                    BindingFlags.NonPublic | BindingFlags.Instance) == null &&
                clientType.GetField(
                    "requirePackagedBackendIdentity",
                    BindingFlags.NonPublic | BindingFlags.Instance) == null,
                "the ordinary Release assembly contains the untrusted backend factory/gate");

            MethodInfo open = identityType.GetMethod(
                "OpenPackage", BindingFlags.NonPublic | BindingFlags.Static);
            MethodInfo revalidate = identityType.GetMethod(
                "RevalidateImmediatelyBeforeProcessCreation",
                BindingFlags.NonPublic | BindingFlags.Instance);
            MethodInfo validateCreated = identityType.GetMethod(
                "ValidateCreatedSuspendedProcess",
                BindingFlags.NonPublic | BindingFlags.Instance);
            MethodInfo validateHandshake = identityType.GetMethod(
                "ValidateHandshake", BindingFlags.NonPublic | BindingFlags.Instance);
            MethodInfo validatedTerminal = commandResultType.GetMethod(
                "ValidatedTerminal", BindingFlags.NonPublic | BindingFlags.Static);
            MethodInfo startSuspended = processType.GetMethod(
                "StartSuspended", BindingFlags.NonPublic | BindingFlags.Static);
            Require(
                open != null && revalidate != null && validateCreated != null &&
                validateHandshake != null && validatedTerminal != null &&
                startSuspended != null,
                "identity/process binding methods are absent");

            string packageRoot = Path.Combine(temporaryRoot, "normal", "nested", "package");
            CopyTree(sourcePackage, packageRoot);
            string module = Path.Combine(packageRoot, "bin", "FacMan.WinForms.exe");
            string backend = Path.Combine(packageRoot, "bin", "facman.exe");
            IDisposable lease = (IDisposable)Invoke(open, null, packageRoot, module);
            try
            {
                revalidate.Invoke(lease, new object[0]);

                string handshake = RunProductInspect(backend, temporaryRoot);
                Invoke(
                    validateHandshake,
                    lease,
                    CreateSuccessResult(validatedTerminal, handshake));
                RequireHandshakeMutationRefused(
                    validateHandshake,
                    validatedTerminal,
                    lease,
                    handshake,
                    "\"build_identity\":\"facman=",
                    "\"build_identity\":\"tampered;facman=",
                    "build identity");
                RequireHandshakeMutationRefused(
                    validateHandshake,
                    validatedTerminal,
                    lease,
                    handshake,
                    "\"protocol_version\":2",
                    "\"protocol_version\":1",
                    "transport protocol");
                RequireHandshakeMutationRefused(
                    validateHandshake,
                    validatedTerminal,
                    lease,
                    handshake,
                    JsonDigest(handshake, "contract_set_sha256"),
                    MutatedDigest(JsonDigest(handshake, "contract_set_sha256")),
                    "contract set");
                RequireHandshakeMutationRefused(
                    validateHandshake,
                    validatedTerminal,
                    lease,
                    handshake,
                    universalLauncherRevision,
                    "0fc25340623131ba86c08dca4fb8a43b18a4520d",
                    "provider revision");
                RequireHandshakeMutationRefused(
                    validateHandshake,
                    validatedTerminal,
                    lease,
                    handshake,
                    "\"availability\":\"unavailable_until_isolation_proof\"",
                    "\"availability\":\"available\"",
                    "route capability");

                bool ancestorRenameDenied = false;
                try
                {
                    Directory.Move(
                        Path.Combine(temporaryRoot, "normal"),
                        Path.Combine(temporaryRoot, "normal-retargeted"));
                }
                catch (IOException) { ancestorRenameDenied = true; }
                catch (UnauthorizedAccessException) { ancestorRenameDenied = true; }
                Require(
                    ancestorRenameDenied,
                    "the stable namespace lease allowed an ancestor directory replacement");

                bool replacementDenied = false;
                try
                {
                    File.WriteAllText(backend, "untrusted replacement");
                }
                catch (IOException) { replacementDenied = true; }
                catch (UnauthorizedAccessException) { replacementDenied = true; }
                Require(replacementDenied, "the stable backend lease allowed replacement");

                bool wrongProcessRejected = false;
                using (Process current = Process.GetCurrentProcess())
                {
                    try { Invoke(validateCreated, lease, current.Handle); }
                    catch (InvalidDataException) { wrongProcessRejected = true; }
                }
                Require(
                    wrongProcessRejected,
                    "a suspended process with the wrong native image identity was accepted");

                Action beforeCreate = (Action)Delegate.CreateDelegate(
                    typeof(Action), lease, revalidate);
                Action<IntPtr> afterCreate = (Action<IntPtr>)Delegate.CreateDelegate(
                    typeof(Action<IntPtr>), lease, validateCreated);
                IDisposable suspended = (IDisposable)Invoke(
                    startSuspended,
                    null,
                    backend,
                    "rpc --stdio",
                    beforeCreate,
                    afterCreate);
                suspended.Dispose();
            }
            finally
            {
                lease.Dispose();
            }

            File.WriteAllText(backend, "untrusted replacement");
            bool mismatchRejected = false;
            try
            {
                IDisposable invalid = (IDisposable)Invoke(
                    open, null, packageRoot, module);
                invalid.Dispose();
            }
            catch (InvalidDataException) { mismatchRejected = true; }
            Require(mismatchRejected, "a backend SHA-256 substitution was accepted");

            string hardlinkPackage = Path.Combine(temporaryRoot, "hardlink-package");
            CopyTree(sourcePackage, hardlinkPackage);
            string hardlinkBackend = Path.Combine(hardlinkPackage, "bin", "facman.exe");
            string externalBackend = Path.Combine(temporaryRoot, "external-facman.exe");
            File.Copy(hardlinkBackend, externalBackend, true);
            File.Delete(hardlinkBackend);
            if (!CreateHardLink(hardlinkBackend, externalBackend, IntPtr.Zero))
                throw new InvalidOperationException(
                    "cannot create hardlink proof: " + Marshal.GetLastWin32Error().ToString());
            bool hardlinkRejected = false;
            try
            {
                IDisposable invalid = (IDisposable)Invoke(
                    open,
                    null,
                    hardlinkPackage,
                    Path.Combine(hardlinkPackage, "bin", "FacMan.WinForms.exe"));
                invalid.Dispose();
            }
            catch (InvalidDataException) { hardlinkRejected = true; }
            Require(hardlinkRejected, "an externally aliased hardlink backend was accepted");

            string junctionTarget = Path.Combine(temporaryRoot, "junction-target");
            string junctionPackage = Path.Combine(junctionTarget, "package");
            CopyTree(sourcePackage, junctionPackage);
            junctionPath = Path.Combine(temporaryRoot, "junction-alias");
            CreateJunction(junctionPath, junctionTarget);
            string aliasedPackage = Path.Combine(junctionPath, "package");
            bool ancestorJunctionRejected = false;
            try
            {
                IDisposable invalid = (IDisposable)Invoke(
                    open,
                    null,
                    aliasedPackage,
                    Path.Combine(aliasedPackage, "bin", "FacMan.WinForms.exe"));
                invalid.Dispose();
            }
            catch (InvalidDataException) { ancestorJunctionRejected = true; }
            Require(
                ancestorJunctionRejected,
                "a package reached through an ancestor junction was accepted");

            Console.WriteLine(
                "winforms-backend-identity-harness: PASS " +
                "(release surface, exact handshake, full namespace lease, native image binding, " +
                "hardlink/junction/substitution refusal)");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.ToString());
            return 1;
        }
        finally
        {
            try
            {
                if (!String.IsNullOrEmpty(junctionPath) && Directory.Exists(junctionPath))
                    Directory.Delete(junctionPath, false);
                if (Directory.Exists(temporaryRoot)) Directory.Delete(temporaryRoot, true);
            }
            catch { }
        }
    }

    private static object Invoke(
        MethodInfo method,
        object target,
        params object[] arguments)
    {
        try { return method.Invoke(target, arguments); }
        catch (TargetInvocationException error)
        {
            if (error.InnerException != null) throw error.InnerException;
            throw;
        }
    }

    private static object CreateSuccessResult(MethodInfo factory, string stdout)
    {
        return Invoke(
            factory,
            null,
            "product.inspect",
            "flb.factorio",
            0,
            stdout,
            String.Empty,
            false,
            String.Empty,
            String.Empty,
            "ok",
            "identity-operation",
            "identity-attempt",
            "completed",
            false,
            false,
            String.Empty,
            String.Empty);
    }

    private static void RequireHandshakeMutationRefused(
        MethodInfo validate,
        MethodInfo factory,
        object lease,
        string valid,
        string original,
        string replacement,
        string label)
    {
        string mutated = valid.Replace(original, replacement);
        Require(!String.Equals(mutated, valid, StringComparison.Ordinal),
            "the " + label + " handshake mutation did not match the backend response");
        bool refused = false;
        try { Invoke(validate, lease, CreateSuccessResult(factory, mutated)); }
        catch (InvalidDataException) { refused = true; }
        Require(refused, "a mismatched " + label + " handshake was accepted");
    }

    private static string JsonDigest(string document, string member)
    {
        string prefix = "\"" + member + "\":\"";
        int start = document.IndexOf(prefix, StringComparison.Ordinal);
        if (start < 0) throw new InvalidOperationException(member + " is absent from the handshake");
        start += prefix.Length;
        if (start + 64 > document.Length)
            throw new InvalidOperationException(member + " is truncated in the handshake");
        return document.Substring(start, 64);
    }

    private static string MutatedDigest(string digest)
    {
        if (digest == null || digest.Length != 64)
            throw new InvalidOperationException("cannot mutate a non-SHA-256 digest");
        return (digest[0] == '0' ? "1" : "0") + digest.Substring(1);
    }

    private static string PackageRevision(string root, string member)
    {
        string prefix = member + " = \"";
        foreach (string line in File.ReadAllLines(
            Path.Combine(root, "manifest", "package.v1.toml")))
        {
            if (line.StartsWith(prefix, StringComparison.Ordinal) && line.EndsWith("\""))
            {
                string value = line.Substring(prefix.Length, line.Length - prefix.Length - 1);
                if (value.Length == 40) return value;
            }
        }
        throw new InvalidDataException("The package provider revision is absent or malformed.");
    }

    private static string RunProductInspect(string backend, string workspaceParent)
    {
        string workspace = Path.Combine(workspaceParent, "inspect-workspace");
        Directory.CreateDirectory(workspace);
        ProcessStartInfo start = new ProcessStartInfo();
        start.FileName = backend;
        start.Arguments = "--workspace \"" + workspace + "\" product inspect --json";
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.StandardOutputEncoding = Encoding.UTF8;
        start.StandardErrorEncoding = Encoding.UTF8;
        using (Process process = Process.Start(start))
        {
            string stdout = process.StandardOutput.ReadToEnd();
            string stderr = process.StandardError.ReadToEnd();
            if (!process.WaitForExit(30000))
            {
                try { process.Kill(); }
                catch { }
                throw new InvalidOperationException("packaged product.inspect timed out");
            }
            if (process.ExitCode != 0)
                throw new InvalidOperationException(
                    "packaged product.inspect failed: " + stderr.Trim());
            string trimmed = stdout.Trim();
            Require(trimmed.StartsWith("{", StringComparison.Ordinal) &&
                trimmed.EndsWith("}", StringComparison.Ordinal),
                "packaged product.inspect did not return one JSON object");
            return trimmed;
        }
    }

    private static void CopyTree(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (string directory in Directory.GetDirectories(
            source, "*", SearchOption.AllDirectories))
            Directory.CreateDirectory(
                Path.Combine(destination, RelativePath(source, directory)));
        foreach (string file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            string target = Path.Combine(destination, RelativePath(source, file));
            Directory.CreateDirectory(Path.GetDirectoryName(target));
            File.Copy(file, target, true);
        }
    }

    private static void CreateJunction(string junction, string target)
    {
        const uint genericWrite = 0x40000000;
        const uint openExisting = 3;
        const uint openReparsePoint = 0x00200000;
        const uint backupSemantics = 0x02000000;
        const uint setReparsePoint = 0x000900A4;
        const uint mountPointTag = 0xA0000003;

        string absoluteTarget = Path.GetFullPath(target);
        string substituteName = @"\??\" + absoluteTarget;
        byte[] substituteBytes = System.Text.Encoding.Unicode.GetBytes(substituteName);
        byte[] printBytes = System.Text.Encoding.Unicode.GetBytes(absoluteTarget);
        byte[] pathBuffer = new byte[
            substituteBytes.Length + sizeof(char) + printBytes.Length + sizeof(char)];
        Buffer.BlockCopy(substituteBytes, 0, pathBuffer, 0, substituteBytes.Length);
        Buffer.BlockCopy(
            printBytes,
            0,
            pathBuffer,
            substituteBytes.Length + sizeof(char),
            printBytes.Length);

        ushort reparseDataLength = checked((ushort)(8 + pathBuffer.Length));
        byte[] reparse = new byte[8 + reparseDataLength];
        WriteUInt32(reparse, 0, mountPointTag);
        WriteUInt16(reparse, 4, reparseDataLength);
        WriteUInt16(reparse, 8, 0);
        WriteUInt16(reparse, 10, checked((ushort)substituteBytes.Length));
        WriteUInt16(
            reparse,
            12,
            checked((ushort)(substituteBytes.Length + sizeof(char))));
        WriteUInt16(reparse, 14, checked((ushort)printBytes.Length));
        Buffer.BlockCopy(pathBuffer, 0, reparse, 16, pathBuffer.Length);

        Directory.CreateDirectory(junction);
        using (SafeFileHandle handle = CreateFile(
            junction,
            genericWrite,
            0,
            IntPtr.Zero,
            openExisting,
            openReparsePoint | backupSemantics,
            IntPtr.Zero))
        {
            if (handle.IsInvalid)
                throw new InvalidOperationException(
                    "cannot open ancestor junction proof: " + Marshal.GetLastWin32Error());
            uint returned;
            if (!DeviceIoControl(
                handle,
                setReparsePoint,
                reparse,
                (uint)reparse.Length,
                IntPtr.Zero,
                0,
                out returned,
                IntPtr.Zero))
                throw new InvalidOperationException(
                    "cannot create ancestor junction proof: " + Marshal.GetLastWin32Error());
        }
    }

    private static void WriteUInt16(byte[] buffer, int offset, ushort value)
    {
        byte[] encoded = BitConverter.GetBytes(value);
        Buffer.BlockCopy(encoded, 0, buffer, offset, encoded.Length);
    }

    private static void WriteUInt32(byte[] buffer, int offset, uint value)
    {
        byte[] encoded = BitConverter.GetBytes(value);
        Buffer.BlockCopy(encoded, 0, buffer, offset, encoded.Length);
    }

    private static string RelativePath(string root, string path)
    {
        string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) +
            Path.DirectorySeparatorChar;
        string full = Path.GetFullPath(path);
        Require(full.StartsWith(prefix, StringComparison.OrdinalIgnoreCase),
            "copied path escapes package root");
        return full.Substring(prefix.Length);
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CreateHardLink(
        string fileName,
        string existingFileName,
        IntPtr securityAttributes);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool DeviceIoControl(
        SafeFileHandle device,
        uint controlCode,
        byte[] input,
        uint inputSize,
        IntPtr output,
        uint outputSize,
        out uint bytesReturned,
        IntPtr overlapped);
}
