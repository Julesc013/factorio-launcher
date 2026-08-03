// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace FacMan.WinForms
{
    /// <summary>
    /// Holds a stable, no-follow identity for every hash-closed package path while
    /// a backend preflight and command are dispatched. Production discovery is
    /// rooted only at the running WinForms module; configured paths are never
    /// consulted by this class.
    /// </summary>
    internal sealed class PackagedBackendIdentity : IDisposable
    {
        private const uint GenericRead = 0x80000000;
        private const uint FileShareRead = 0x00000001;
        private const uint FileShareWrite = 0x00000002;
        private const uint FileShareDelete = 0x00000004;
        private const uint OpenExisting = 3;
        private const uint FileFlagBackupSemantics = 0x02000000;
        private const uint FileFlagOpenReparsePoint = 0x00200000;
        private const uint FileAttributeReparsePoint = 0x00000400;
        private const uint FileAttributeDirectory = 0x00000010;
        private const uint VolumeNameNt = 0x00000002;
        private const uint ProcessNameNative = 0x00000001;
        private const int ErrorInsufficientBuffer = 122;
        private const int MaximumManifestBytes = 16 * 1024 * 1024;
        private const int MaximumPackageEntries = 100000;
        private const string AcceptedUniversalLauncherRevision =
            "7fc25340623131ba86c08dca4fb8a43b18a4520d";
        private const string AcceptedUniversalSetupRevision =
            "3048128963dc718a7c38c1cfcdda9e813a23b0db";

        private static readonly UTF8Encoding StrictUtf8 = new UTF8Encoding(false, true);
        private readonly Dictionary<string, StablePath> stablePaths;
        private readonly Dictionary<string, string> declaredHashes;
        private readonly List<string> namespaceComponents;
        private readonly PackageExpectation expectation;
        private readonly string packageRoot;
        private readonly string backendPackagePath;
        private readonly bool trustedPackage;
        private bool disposed;

#if FACMAN_TRANSPORT_HARNESS
        private PackagedBackendIdentity(string executablePath)
        {
            ExecutablePath = executablePath;
            packageRoot = String.Empty;
            backendPackagePath = executablePath;
            stablePaths = new Dictionary<string, StablePath>(StringComparer.OrdinalIgnoreCase);
            declaredHashes = new Dictionary<string, string>(StringComparer.Ordinal);
            namespaceComponents = new List<string>();
            trustedPackage = false;
        }
#endif

        private PackagedBackendIdentity(
            string root,
            string executablePath,
            Dictionary<string, StablePath> paths,
            Dictionary<string, string> hashes,
            List<string> components,
            PackageExpectation expected)
        {
            packageRoot = root;
            stablePaths = paths;
            declaredHashes = hashes;
            namespaceComponents = components;
            expectation = expected;
            backendPackagePath = Path.GetFullPath(executablePath);
            ExecutablePath = paths[backendPackagePath].GlobalRootPath;
            trustedPackage = true;
        }

        internal string ExecutablePath { get; private set; }

        internal static PackagedBackendIdentity OpenProduction()
        {
            if (Environment.OSVersion.Platform != PlatformID.Win32NT)
                throw new PlatformNotSupportedException(
                    "Packaged WinForms backend identity requires Windows.");
            string module = RunningModulePath();
            string bin = Path.GetDirectoryName(module);
            string root = String.IsNullOrEmpty(bin) ? null : Path.GetDirectoryName(bin);
            if (String.IsNullOrEmpty(root))
                throw Invalid("The running WinForms module has no package root.");
            return OpenPackageBound(
                root,
                module,
                ProcessImageNativePath(GetCurrentProcess()));
        }

#if FACMAN_TRANSPORT_HARNESS
        /// <summary>
        /// The existing transport harness deliberately exercises transport law
        /// with a synthetic executable. This path is internal, bypasses package
        /// trust, and is not reachable from public production constructors.
        /// </summary>
        internal static PackagedBackendIdentity OpenUntrustedTransportTest(string path)
        {
            return new PackagedBackendIdentity(path == null ? String.Empty : path.Trim());
        }
#endif

        internal void RevalidateImmediatelyBeforeProcessCreation()
        {
            ThrowIfDisposed();
            if (!trustedPackage) return;
            ValidateNamespaceComponents(namespaceComponents);
            foreach (StablePath path in stablePaths.Values) path.Revalidate();
            ValidatePackageClosure(packageRoot, declaredHashes, stablePaths, expectation);
            ValidateNamespaceComponents(namespaceComponents);
            foreach (StablePath path in stablePaths.Values) path.Revalidate();
            stablePaths[backendPackagePath].Revalidate();
        }

        internal void ValidateCreatedSuspendedProcess(IntPtr processHandle)
        {
            ThrowIfDisposed();
            if (!trustedPackage) return;
            if (processHandle == IntPtr.Zero)
                throw Invalid("The suspended backend process has no process handle.");

            StablePath expected = stablePaths[backendPackagePath];
            expected.Revalidate();
            string actualNativePath = ProcessImageNativePath(processHandle);
            if (!String.Equals(
                actualNativePath, expected.FinalNativePath, StringComparison.OrdinalIgnoreCase))
                throw Invalid(
                    "The suspended backend image path does not match the stable package backend.");

            string globalRootPath = @"\\?\GLOBALROOT" + actualNativePath;
            using (StablePath actual = StablePath.Open(globalRootPath, false))
            {
                if (!expected.SameFile(actual))
                    throw Invalid(
                        "The suspended backend image file identity does not match the stable package backend.");
            }
        }

        internal void ValidateHandshake(CommandResult result)
        {
            ThrowIfDisposed();
            if (!trustedPackage) return;
            if (result == null || !result.Success)
                throw Invalid("The backend identity preflight did not complete successfully.");

            Dictionary<string, object> envelope = StrictTransportJson.ParseObject(
                result.Stdout, MaximumManifestBytes);
            Dictionary<string, object> payload = RequiredObject(envelope, "payload", "response envelope");
            Dictionary<string, object> identity = RequiredObject(
                payload, "backend_identity", "product.inspect payload");
            RequireExactMembers(
                identity,
                "backend identity",
                "schema",
                "product_id",
                "binding_id",
                "backend_role",
                "build",
                "transport",
                "command_catalog_sha256",
                "contract_set_sha256",
                "package",
                "run_execute");
            RequireText(identity, "schema", "facman.backend_identity.v1", "backend identity");
            RequireText(identity, "product_id", "factorio", "backend identity");
            RequireText(identity, "binding_id", "flb.factorio", "backend identity");
            RequireText(identity, "backend_role", "facman_cli", "backend identity");
            RequireText(
                identity,
                "command_catalog_sha256",
                GeneratedCommandCatalog.CommandCatalogSha256,
                "backend identity");
            RequireText(
                identity,
                "contract_set_sha256",
                GeneratedCommandCatalog.ContractSetSha256,
                "backend identity");

            ValidateBuild(RequiredObject(identity, "build", "backend identity"));
            ValidateTransport(RequiredObject(identity, "transport", "backend identity"));
            ValidatePackage(RequiredObject(identity, "package", "backend identity"));
            ValidateRunExecute(RequiredObject(identity, "run_execute", "backend identity"));
        }

        public void Dispose()
        {
            if (disposed) return;
            disposed = true;
            foreach (StablePath path in stablePaths.Values) path.Dispose();
            stablePaths.Clear();
        }

        private static PackagedBackendIdentity OpenPackage(string rootPath, string modulePath)
        {
            return OpenPackageBound(rootPath, modulePath, null);
        }

        private static PackagedBackendIdentity OpenPackageBound(
            string rootPath,
            string modulePath,
            string runningImageNativePath)
        {
            string root = Path.GetFullPath(rootPath);
            string module = Path.GetFullPath(modulePath);
            string expectedModule = Path.Combine(root, "bin", "FacMan.WinForms.exe");
            if (!String.Equals(module, expectedModule, StringComparison.OrdinalIgnoreCase))
                throw Invalid(
                    "The running WinForms module is not the package entrypoint bin/FacMan.WinForms.exe.");

            Dictionary<string, StablePath> paths =
                new Dictionary<string, StablePath>(StringComparer.OrdinalIgnoreCase);
            List<string> namespacePaths = new List<string>();
            try
            {
                OpenDirectoryChain(paths, root, namespacePaths);
                AddStable(paths, Path.Combine(root, "bin"), true);
                AddStable(paths, Path.Combine(root, "manifest"), true);
                AddStable(paths, module, false);
                if (!String.IsNullOrEmpty(runningImageNativePath))
                {
                    StablePath stableModule = paths[Path.GetFullPath(module)];
                    if (!String.Equals(
                        stableModule.FinalNativePath,
                        runningImageNativePath,
                        StringComparison.OrdinalIgnoreCase))
                        throw Invalid(
                            "The running WinForms image does not match its package module path.");
                    using (StablePath runningImage = StablePath.Open(
                        @"\\?\GLOBALROOT" + runningImageNativePath, false))
                    {
                        if (!stableModule.SameFile(runningImage))
                            throw Invalid(
                                "The running WinForms image file identity does not match its package module.");
                    }
                }

                string packagePath = Path.Combine(root, "manifest", "package.v1.toml");
                string buildInfoPath = Path.Combine(root, "manifest", "build_info.v1.json");
                string componentsPath = Path.Combine(root, "manifest", "components.v1.json");
                string hashesPath = Path.Combine(root, "manifest", "hashes.sha256");
                string backendPath = Path.Combine(root, "bin", "facman.exe");
                AddStable(paths, packagePath, false);
                AddStable(paths, buildInfoPath, false);
                AddStable(paths, componentsPath, false);
                AddStable(paths, hashesPath, false);
                AddStable(paths, backendPath, false);

                byte[] packageBytes = ReadBounded(packagePath, MaximumManifestBytes);
                byte[] buildInfoBytes = ReadBounded(buildInfoPath, MaximumManifestBytes);
                byte[] componentBytes = ReadBounded(componentsPath, MaximumManifestBytes);
                byte[] hashBytes = ReadBounded(hashesPath, MaximumManifestBytes);
                PackageExpectation expected = ParsePackage(
                    packageBytes, buildInfoBytes, componentBytes, hashBytes, backendPath);
                Dictionary<string, string> hashes = ParseHashManifest(hashBytes);

                OpenCompleteTree(root, paths);
                ValidatePackageClosure(root, hashes, paths, expected);
                return new PackagedBackendIdentity(
                    root, backendPath, paths, hashes, namespacePaths, expected);
            }
            catch
            {
                foreach (StablePath path in paths.Values) path.Dispose();
                throw;
            }
        }

        private static PackageExpectation ParsePackage(
            byte[] packageBytes,
            byte[] buildInfoBytes,
            byte[] componentBytes,
            byte[] hashBytes,
            string backendPath)
        {
            Dictionary<string, object> package = ParseFlatToml(packageBytes);
            RequireExactMembers(
                package,
                "built package manifest",
                "schema",
                "profile_id",
                "lane",
                "target_os",
                "target_arch",
                "package_type",
                "entrypoint",
                "linkage_model",
                "release_profile",
                "package_manifest",
                "workspace_lock",
                "source_revision",
                "proof_baseline_revision",
                "universal_launcher_revision",
                "universal_setup_revision",
                "artifact_level",
                "signed",
                "published",
                "source_dirty",
                "python_runtime",
                "bundles_factorio_binaries");
            RequireText(package, "schema", "facman.built_package.v1", "built package manifest");
            RequireText(
                package,
                "profile_id",
                "windows_legacy_winforms_x64",
                "built package manifest");
            RequireText(package, "lane", "windows_legacy_winforms", "built package manifest");
            RequireText(package, "target_os", "windows", "built package manifest");
            RequireText(package, "target_arch", "x64", "built package manifest");
            RequireText(package, "package_type", "portable_zip", "built package manifest");
            RequireText(
                package, "entrypoint", "bin/FacMan.WinForms.exe", "built package manifest");
            RequireText(
                package, "linkage_model", "compatibility_bundle", "built package manifest");
            RequireText(
                package,
                "release_profile",
                "release/profiles/windows_legacy_winforms_x64/profile.toml",
                "built package manifest");
            RequireText(
                package,
                "package_manifest",
                "release/packaging/windows/facman_portable.v1.toml",
                "built package manifest");
            RequireText(
                package,
                "workspace_lock",
                "release/index/workspace_lock.v1.toml",
                "built package manifest");
            RequireText(package, "artifact_level", "built-artifact", "built package manifest");
            RequireBoolean(package, "signed", false, "built package manifest");
            RequireBoolean(package, "published", false, "built package manifest");
            RequireBoolean(package, "python_runtime", false, "built package manifest");
            RequireBoolean(
                package, "bundles_factorio_binaries", false, "built package manifest");

            string sourceRevision = RequiredHex(package, "source_revision", 40, "built package manifest");
            string universalLauncher = RequiredHex(
                package, "universal_launcher_revision", 40, "built package manifest");
            string universalSetup = RequiredHex(
                package, "universal_setup_revision", 40, "built package manifest");
            if (!String.Equals(
                universalLauncher, AcceptedUniversalLauncherRevision, StringComparison.Ordinal) ||
                !String.Equals(
                    universalSetup, AcceptedUniversalSetupRevision, StringComparison.Ordinal))
                throw Invalid(
                    "The package provider revisions are not the separately accepted FacMan pins.");
            RequiredHex(package, "proof_baseline_revision", 40, "built package manifest");
            bool sourceDirty = RequiredBoolean(package, "source_dirty", "built package manifest");

            Dictionary<string, object> buildInfo = StrictTransportJson.ParseObject(
                DecodeStrict(buildInfoBytes, "build info"), MaximumManifestBytes);
            RequireExactMembers(
                buildInfo,
                "build info",
                "schema",
                "profile_id",
                "artifact_level",
                "canonical_version",
                "filename_version",
                "source_commit",
                "source_timestamp_policy",
                "source_timestamp_utc",
                "source_dirty",
                "source_state_sha256",
                "source_revisions",
                "target_os",
                "target_arch",
                "package_type",
                "signed",
                "published",
                "toolchain");
            RequireText(buildInfo, "schema", "facman.package_build_info.v1", "build info");
            RequireText(
                buildInfo,
                "profile_id",
                "windows_legacy_winforms_x64",
                "build info");
            RequireText(buildInfo, "artifact_level", "built-artifact", "build info");
            RequireText(buildInfo, "source_commit", sourceRevision, "build info");
            RequireText(buildInfo, "target_os", "windows", "build info");
            RequireText(buildInfo, "target_arch", "x64", "build info");
            RequireText(buildInfo, "package_type", "portable_zip", "build info");
            RequireBoolean(buildInfo, "source_dirty", sourceDirty, "build info");
            RequireBoolean(buildInfo, "signed", false, "build info");
            RequireBoolean(buildInfo, "published", false, "build info");
            RequiredHex(buildInfo, "source_state_sha256", 64, "build info");
            RequiredNonEmptyText(buildInfo, "canonical_version", "build info");
            RequiredNonEmptyText(buildInfo, "filename_version", "build info");
            RequiredNonEmptyText(buildInfo, "source_timestamp_policy", "build info");
            RequiredNonEmptyText(buildInfo, "source_timestamp_utc", "build info");
            RequiredObject(buildInfo, "toolchain", "build info");
            Dictionary<string, object> revisions = RequiredObject(
                buildInfo, "source_revisions", "build info");
            RequireExactMembers(
                revisions,
                "build source revisions",
                "factorio_launcher",
                "universal_launcher",
                "universal_setup");
            RequireText(revisions, "factorio_launcher", sourceRevision, "build source revisions");
            RequireText(
                revisions, "universal_launcher", universalLauncher, "build source revisions");
            RequireText(revisions, "universal_setup", universalSetup, "build source revisions");

            Dictionary<string, object> components = StrictTransportJson.ParseObject(
                DecodeStrict(componentBytes, "component manifest"), MaximumManifestBytes);
            RequireExactMembers(components, "component manifest", "schema", "components");
            RequireText(
                components, "schema", "facman.package_components.v1", "component manifest");
            object[] componentRecords = RequiredArray(components, "components", "component manifest");
            if (componentRecords.Length == 0) throw Invalid("The component manifest is empty.");
            string backendHash = null;
            long backendSize = -1;
            HashSet<string> destinations = new HashSet<string>(StringComparer.Ordinal);
            foreach (object value in componentRecords)
            {
                Dictionary<string, object> record = value as Dictionary<string, object>;
                if (record == null) throw Invalid("A component manifest record is not an object.");
                HashSet<string> allowed = new HashSet<string>(
                    new string[] {
                        "name", "source_target", "destination", "container_destination",
                        "kind", "runtime_role", "sha256", "size"
                    },
                    StringComparer.Ordinal);
                RequireMembers(record, "component record", allowed,
                    "name", "source_target", "destination", "kind", "runtime_role", "sha256", "size");
                string destination = RequiredNonEmptyText(record, "destination", "component record");
                if (!SafeRelativePath(destination) || !destinations.Add(destination))
                    throw Invalid("The component manifest has an unsafe or duplicate destination.");
                RequiredNonEmptyText(record, "name", "component record");
                RequiredNonEmptyText(record, "source_target", "component record");
                RequiredNonEmptyText(record, "kind", "component record");
                RequiredNonEmptyText(record, "runtime_role", "component record");
                string digest = RequiredHex(record, "sha256", 64, "component record");
                long size = RequiredNonNegativeInteger(record, "size", "component record");
                if (record.ContainsKey("container_destination"))
                    RequiredNonEmptyText(record, "container_destination", "component record");
                if (String.Equals(destination, "bin/facman.exe", StringComparison.Ordinal))
                {
                    if (backendHash != null)
                        throw Invalid("The package declares more than one facman backend component.");
                    RequireText(record, "name", "console_cli", "backend component");
                    RequireText(record, "source_target", "facman_cli", "backend component");
                    RequireText(record, "kind", "frontend", "backend component");
                    RequireText(record, "runtime_role", "runtime_required", "backend component");
                    backendHash = digest;
                    backendSize = size;
                }
            }
            if (backendHash == null)
                throw Invalid("The package has no exact bin/facman.exe component record.");

            return new PackageExpectation(
                sourceRevision,
                sourceDirty,
                universalLauncher,
                universalSetup,
                backendHash,
                backendSize,
                Sha256(packageBytes),
                Sha256(hashBytes));
        }

        private static Dictionary<string, string> ParseHashManifest(byte[] bytes)
        {
            string text = DecodeStrict(bytes, "hash manifest");
            Dictionary<string, string> result =
                new Dictionary<string, string>(StringComparer.Ordinal);
            string[] lines = text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
            foreach (string line in lines)
            {
                if (line.Length == 0) continue;
                if (line.Length < 67 || line.Substring(64, 2) != "  ")
                    throw Invalid("The hash manifest contains an invalid record.");
                string digest = line.Substring(0, 64);
                string relative = line.Substring(66);
                if (!IsLowerHex(digest, 64) || !SafeRelativePath(relative) ||
                    relative == "manifest/hashes.sha256" || relative.EndsWith(".sig", StringComparison.Ordinal) ||
                    result.ContainsKey(relative))
                    throw Invalid("The hash manifest contains an unsafe or duplicate record.");
                result.Add(relative, digest);
                if (result.Count > MaximumPackageEntries)
                    throw Invalid("The hash manifest exceeds its entry budget.");
            }
            if (result.Count == 0) throw Invalid("The hash manifest is empty.");
            return result;
        }

        private static void OpenCompleteTree(
            string root,
            Dictionary<string, StablePath> paths)
        {
            Stack<string> pending = new Stack<string>();
            pending.Push(root);
            int entries = 0;
            while (pending.Count > 0)
            {
                string directory = pending.Pop();
                AddStable(paths, directory, true);
                string[] children = Directory.GetFileSystemEntries(directory);
                Array.Sort(children, StringComparer.OrdinalIgnoreCase);
                foreach (string child in children)
                {
                    if (++entries > MaximumPackageEntries)
                        throw Invalid("The package exceeds its path budget.");
                    FileAttributes attributes = File.GetAttributes(child);
                    if ((attributes & FileAttributes.ReparsePoint) != 0)
                        throw Invalid("The package contains a linked or reparse path: " + child);
                    if ((attributes & FileAttributes.Directory) != 0)
                    {
                        AddStable(paths, child, true);
                        pending.Push(child);
                    }
                    else
                    {
                        AddStable(paths, child, false);
                    }
                }
            }
        }

        private static void ValidatePackageClosure(
            string root,
            Dictionary<string, string> hashes,
            Dictionary<string, StablePath> paths,
            PackageExpectation expected)
        {
            HashSet<string> actual = EnumerateHashClosedFiles(root);
            if (!actual.SetEquals(hashes.Keys))
                throw Invalid("The package file closure differs from manifest/hashes.sha256.");
            foreach (KeyValuePair<string, string> record in hashes)
            {
                string full = ResolveUnderRoot(root, record.Key);
                StablePath stable;
                if (!paths.TryGetValue(full, out stable) || stable.IsDirectory)
                    throw Invalid("A hash-declared package file has no stable no-follow identity.");
                stable.Revalidate();
                string actualHash = Sha256File(full);
                if (!String.Equals(actualHash, record.Value, StringComparison.Ordinal))
                    throw Invalid("Package SHA-256 mismatch: " + record.Key);
            }

            string backendRelative = "bin/facman.exe";
            string declaredBackend;
            if (!hashes.TryGetValue(backendRelative, out declaredBackend) ||
                !String.Equals(declaredBackend, expected.BackendSha256, StringComparison.Ordinal))
                throw Invalid("The backend component and package hash manifests disagree.");
            StablePath backend = paths[Path.GetFullPath(Path.Combine(root, "bin", "facman.exe"))];
            if (backend.Length != expected.BackendSize)
                throw Invalid("The backend component size does not match its stable file identity.");

            string packageHash;
            if (!hashes.TryGetValue("manifest/package.v1.toml", out packageHash) ||
                !String.Equals(packageHash, expected.ManifestSha256, StringComparison.Ordinal))
                throw Invalid("The built package manifest digest is not hash-closed.");

            string contractDigest = ContractSetSha256(root, actual);
            if (!String.Equals(
                contractDigest, GeneratedCommandCatalog.ContractSetSha256, StringComparison.Ordinal))
                throw Invalid("The package contract set does not match the compiled frontend contract set.");
            expected.ContractSetSha256 = contractDigest;
            expected.FilesVerified = hashes.Count;
        }

        private void ValidateBuild(Dictionary<string, object> build)
        {
            RequireExactMembers(
                build,
                "backend build identity",
                "source_revision",
                "source_dirty",
                "build_identity",
                "universal_launcher_revision",
                "universal_setup_revision");
            RequireText(
                build, "source_revision", expectation.SourceRevision, "backend build identity");
            RequireBoolean(
                build, "source_dirty", expectation.SourceDirty, "backend build identity");
            RequireText(
                build, "build_identity", expectation.BuildIdentity, "backend build identity");
            RequireText(
                build,
                "universal_launcher_revision",
                expectation.UniversalLauncherRevision,
                "backend build identity");
            RequireText(
                build,
                "universal_setup_revision",
                expectation.UniversalSetupRevision,
                "backend build identity");
        }

        private static void ValidateTransport(Dictionary<string, object> transport)
        {
            RequireExactMembers(
                transport,
                "backend transport identity",
                "protocol_version",
                "request_schema",
                "response_schema");
            RequireInteger(transport, "protocol_version", 2, "backend transport identity");
            RequireText(
                transport,
                "request_schema",
                "facman.transport_request.v2",
                "backend transport identity");
            RequireText(
                transport,
                "response_schema",
                "facman.transport_response.v2",
                "backend transport identity");
        }

        private void ValidatePackage(Dictionary<string, object> package)
        {
            RequireExactMembers(
                package,
                "backend package identity",
                "mode",
                "integrity",
                "verified",
                "profile_id",
                "manifest_sha256",
                "closure_sha256",
                "contract_set_sha256",
                "contract_set_matches_build",
                "backend_relative_path",
                "backend_sha256",
                "source_revision",
                "source_dirty",
                "universal_launcher_revision",
                "universal_setup_revision",
                "build_matches_package",
                "files_verified",
                "authenticity",
                "detail");
            RequireText(package, "mode", "packaged", "backend package identity");
            RequireText(
                package, "integrity", "sha256_consistent", "backend package identity");
            RequireBoolean(package, "verified", true, "backend package identity");
            RequireText(
                package,
                "profile_id",
                "windows_legacy_winforms_x64",
                "backend package identity");
            RequireText(
                package, "manifest_sha256", expectation.ManifestSha256, "backend package identity");
            RequireText(
                package, "closure_sha256", expectation.ClosureSha256, "backend package identity");
            RequireText(
                package,
                "contract_set_sha256",
                expectation.ContractSetSha256,
                "backend package identity");
            RequireBoolean(
                package, "contract_set_matches_build", true, "backend package identity");
            RequireText(
                package, "backend_relative_path", "bin/facman.exe", "backend package identity");
            RequireText(
                package, "backend_sha256", expectation.BackendSha256, "backend package identity");
            RequireText(
                package, "source_revision", expectation.SourceRevision, "backend package identity");
            RequireBoolean(
                package, "source_dirty", expectation.SourceDirty, "backend package identity");
            RequireText(
                package,
                "universal_launcher_revision",
                expectation.UniversalLauncherRevision,
                "backend package identity");
            RequireText(
                package,
                "universal_setup_revision",
                expectation.UniversalSetupRevision,
                "backend package identity");
            RequireBoolean(package, "build_matches_package", true, "backend package identity");
            RequireInteger(
                package, "files_verified", expectation.FilesVerified, "backend package identity");
            RequireText(
                package,
                "authenticity",
                "not_proven_unsigned",
                "backend package identity");
            RequiredNonEmptyText(package, "detail", "backend package identity");
        }

        private static void ValidateRunExecute(Dictionary<string, object> capability)
        {
            RequireExactMembers(
                capability,
                "run.execute capability",
                "command",
                "availability",
                "refusal_code",
                "enabled");
            CommandDefinition expected = GeneratedCommandCatalog.Find("run.execute");
            bool enabled = expected.Status == CommandStatus.Implemented &&
                String.Equals(expected.Availability, "available", StringComparison.Ordinal);
            RequireText(capability, "command", "run.execute", "run.execute capability");
            RequireText(
                capability, "availability", expected.Availability, "run.execute capability");
            RequireText(
                capability, "refusal_code", enabled ? String.Empty : expected.DeferredReason,
                "run.execute capability", true);
            RequireBoolean(capability, "enabled", enabled, "run.execute capability");
        }

        private static HashSet<string> EnumerateHashClosedFiles(string root)
        {
            HashSet<string> result = new HashSet<string>(StringComparer.Ordinal);
            Stack<string> pending = new Stack<string>();
            pending.Push(root);
            int entries = 0;
            while (pending.Count > 0)
            {
                string directory = pending.Pop();
                foreach (string path in Directory.GetFileSystemEntries(directory))
                {
                    if (++entries > MaximumPackageEntries)
                        throw Invalid("The package exceeds its path budget.");
                    FileAttributes attributes = File.GetAttributes(path);
                    if ((attributes & FileAttributes.ReparsePoint) != 0)
                        throw Invalid("The package contains a linked or reparse path.");
                    if ((attributes & FileAttributes.Directory) != 0)
                    {
                        pending.Push(path);
                        continue;
                    }
                    string relative = RelativePath(root, path);
                    if (relative == "manifest/hashes.sha256" ||
                        relative.EndsWith(".sig", StringComparison.Ordinal))
                        continue;
                    if (!result.Add(relative))
                        throw Invalid("The package contains a duplicate normalized path.");
                }
            }
            return result;
        }

        private static string ContractSetSha256(string root, IEnumerable<string> packageFiles)
        {
            List<string> schemas = new List<string>();
            foreach (string relative in packageFiles)
                if (relative.StartsWith("contracts/schema/", StringComparison.Ordinal))
                    schemas.Add(relative);
            schemas.Sort(StringComparer.Ordinal);
            if (schemas.Count == 0) throw Invalid("The package contains no contract schema set.");
            using (SHA256 sha = SHA256.Create())
            {
                foreach (string relative in schemas)
                {
                    Transform(sha, StrictUtf8.GetBytes(relative));
                    Transform(sha, new byte[] { 0 });
                    byte[] contents = File.ReadAllBytes(ResolveUnderRoot(root, relative));
                    Transform(sha, NormalizeLineEndings(contents));
                    Transform(sha, new byte[] { 0 });
                }
                sha.TransformFinalBlock(new byte[0], 0, 0);
                return Hex(sha.Hash);
            }
        }

        private static byte[] NormalizeLineEndings(byte[] value)
        {
            using (MemoryStream output = new MemoryStream(value.Length))
            {
                for (int index = 0; index < value.Length; ++index)
                {
                    byte current = value[index];
                    if (current == 13)
                    {
                        if (index + 1 < value.Length && value[index + 1] == 10) index++;
                        output.WriteByte(10);
                    }
                    else output.WriteByte(current);
                }
                return output.ToArray();
            }
        }

        private static void Transform(HashAlgorithm hash, byte[] bytes)
        {
            if (bytes.Length > 0) hash.TransformBlock(bytes, 0, bytes.Length, null, 0);
        }

        private static void AddStable(
            Dictionary<string, StablePath> paths,
            string path,
            bool directory,
            bool allowDeleteSharing = false)
        {
            string full = Path.GetFullPath(path);
            StablePath existing;
            if (paths.TryGetValue(full, out existing))
            {
                if (existing.IsDirectory != directory)
                    throw Invalid("A package path changed type while it was opened.");
                return;
            }
            paths.Add(full, StablePath.Open(full, directory, allowDeleteSharing));
        }

        private static void OpenDirectoryChain(
            Dictionary<string, StablePath> paths,
            string directory,
            List<string> namespacePaths)
        {
            Stack<string> chain = new Stack<string>();
            DirectoryInfo current = new DirectoryInfo(Path.GetFullPath(directory));
            while (current != null)
            {
                chain.Push(current.FullName);
                current = current.Parent;
            }
            if (chain.Count == 0)
                throw Invalid("The package root has no bindable Windows namespace.");
            string packageRootPath = Path.GetFullPath(directory);
            while (chain.Count > 0)
            {
                string component = chain.Pop();
                string fullComponent = Path.GetFullPath(component);
                namespacePaths.Add(fullComponent);
                ValidateNamespaceComponent(fullComponent);
                bool ambient = !String.Equals(
                    fullComponent,
                    packageRootPath,
                    StringComparison.OrdinalIgnoreCase);
                try { AddStable(paths, fullComponent, true, ambient); }
                catch (Win32Exception error)
                {
                    // Some ordinary Windows profile roots deny directory-handle opens even
                    // with zero desired access. They are audited and re-resolved, while the
                    // package root and all launch inputs retain strict handles.
                    if (!ambient || error.NativeErrorCode != 5) throw;
                }
            }
        }

        private static void ValidateNamespaceComponents(IEnumerable<string> paths)
        {
            foreach (string path in paths) ValidateNamespaceComponent(path);
        }

        private static void ValidateNamespaceComponent(string path)
        {
            FileAttributes attributes = File.GetAttributes(path);
            if ((attributes & FileAttributes.Directory) == 0 ||
                (attributes & FileAttributes.ReparsePoint) != 0)
                throw Invalid(
                    "The package launch namespace contains a linked, reparse-backed, or non-directory component: " +
                    path);
        }

        private static string ProcessImageNativePath(IntPtr processHandle)
        {
            uint capacity = 1024;
            while (capacity <= 32768)
            {
                StringBuilder buffer = new StringBuilder((int)capacity);
                uint size = capacity;
                if (QueryFullProcessImageName(
                    processHandle, ProcessNameNative, buffer, ref size))
                    return buffer.ToString();
                int error = Marshal.GetLastWin32Error();
                if (error != ErrorInsufficientBuffer)
                    throw new Win32Exception(
                        error, "Cannot query the suspended backend native image path.");
                capacity *= 2;
            }
            throw Invalid("The suspended backend native image path exceeds the Windows path budget.");
        }

        private static string RunningModulePath()
        {
            StringBuilder buffer = new StringBuilder(1024);
            while (true)
            {
                uint length = GetModuleFileName(IntPtr.Zero, buffer, buffer.Capacity);
                if (length == 0) throw new Win32Exception(Marshal.GetLastWin32Error());
                if (length < buffer.Capacity - 1) return Path.GetFullPath(buffer.ToString());
                if (buffer.Capacity >= 32768)
                    throw Invalid("The running module path exceeds the Windows path budget.");
                buffer.Capacity *= 2;
            }
        }

        private static Dictionary<string, object> ParseFlatToml(byte[] bytes)
        {
            string text = DecodeStrict(bytes, "built package manifest");
            Dictionary<string, object> result =
                new Dictionary<string, object>(StringComparer.Ordinal);
            string[] lines = text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
            foreach (string source in lines)
            {
                string line = source.Trim();
                if (line.Length == 0) continue;
                int separator = line.IndexOf('=');
                if (separator <= 0 || line.IndexOf('=', separator + 1) >= 0)
                    throw Invalid("The built package manifest is not strict flat TOML.");
                string key = line.Substring(0, separator).Trim();
                string scalar = line.Substring(separator + 1).Trim();
                if (!IsTomlKey(key) || result.ContainsKey(key))
                    throw Invalid("The built package manifest contains an invalid or duplicate key.");
                object value;
                if (scalar == "true") value = true;
                else if (scalar == "false") value = false;
                else if (scalar.Length >= 2 && scalar[0] == '"' &&
                    scalar[scalar.Length - 1] == '"')
                    value = ParseTomlString(scalar.Substring(1, scalar.Length - 2));
                else throw Invalid("The built package manifest contains an unsupported scalar.");
                result.Add(key, value);
            }
            return result;
        }

        private static string ParseTomlString(string source)
        {
            StringBuilder result = new StringBuilder(source.Length);
            for (int index = 0; index < source.Length; ++index)
            {
                char ch = source[index];
                if (ch != '\\')
                {
                    if (ch < 0x20 || ch == '"')
                        throw Invalid("The built package manifest contains an invalid string.");
                    result.Append(ch);
                    continue;
                }
                if (++index >= source.Length)
                    throw Invalid("The built package manifest contains an incomplete escape.");
                char escaped = source[index];
                if (escaped == '\\' || escaped == '"') result.Append(escaped);
                else if (escaped == 'n') result.Append('\n');
                else if (escaped == 'r') result.Append('\r');
                else if (escaped == 't') result.Append('\t');
                else throw Invalid("The built package manifest contains an unsupported escape.");
            }
            return result.ToString();
        }

        private static bool IsTomlKey(string value)
        {
            if (String.IsNullOrEmpty(value)) return false;
            foreach (char ch in value)
                if (!(ch >= 'a' && ch <= 'z') && ch != '_') return false;
            return true;
        }

        private static byte[] ReadBounded(string path, int maximum)
        {
            FileInfo info = new FileInfo(path);
            if (info.Length < 0 || info.Length > maximum)
                throw Invalid("A package identity manifest exceeds its byte budget.");
            return File.ReadAllBytes(path);
        }

        private static string DecodeStrict(byte[] bytes, string label)
        {
            try { return StrictUtf8.GetString(bytes); }
            catch (DecoderFallbackException ex)
            {
                throw new InvalidDataException("The " + label + " is not strict UTF-8.", ex);
            }
        }

        private static string RelativePath(string root, string path)
        {
            string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) +
                Path.DirectorySeparatorChar;
            string fullPath = Path.GetFullPath(path);
            if (!fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
                throw Invalid("A package path escapes its root.");
            return fullPath.Substring(fullRoot.Length).Replace('\\', '/');
        }

        private static string ResolveUnderRoot(string root, string relative)
        {
            if (!SafeRelativePath(relative)) throw Invalid("A package path is unsafe.");
            string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) +
                Path.DirectorySeparatorChar;
            string full = Path.GetFullPath(Path.Combine(root, relative.Replace('/', '\\')));
            if (!full.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
                throw Invalid("A package path escapes its root.");
            return full;
        }

        private static bool SafeRelativePath(string value)
        {
            if (String.IsNullOrEmpty(value) || value[0] == '/' || value[value.Length - 1] == '/' ||
                value.IndexOf('\\') >= 0 || value.IndexOf(':') >= 0 || value.IndexOf('\0') >= 0)
                return false;
            string[] segments = value.Split('/');
            foreach (string segment in segments)
                if (segment.Length == 0 || segment == "." || segment == "..") return false;
            return true;
        }

        private static string Sha256(byte[] bytes)
        {
            using (SHA256 sha = SHA256.Create()) return Hex(sha.ComputeHash(bytes));
        }

        private static string Sha256File(string path)
        {
            using (FileStream stream = new FileStream(
                path, FileMode.Open, FileAccess.Read, FileShare.Read, 1024 * 1024,
                FileOptions.SequentialScan))
            using (SHA256 sha = SHA256.Create())
                return Hex(sha.ComputeHash(stream));
        }

        private static string Hex(byte[] bytes)
        {
            StringBuilder result = new StringBuilder(bytes.Length * 2);
            foreach (byte value in bytes) result.Append(value.ToString("x2", CultureInfo.InvariantCulture));
            return result.ToString();
        }

        private static bool IsLowerHex(string value, int length)
        {
            if (value == null || value.Length != length) return false;
            foreach (char ch in value)
                if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return false;
            return true;
        }

        private static void RequireExactMembers(
            Dictionary<string, object> value,
            string label,
            params string[] expected)
        {
            RequireMembers(
                value,
                label,
                new HashSet<string>(expected, StringComparer.Ordinal),
                expected);
        }

        private static void RequireMembers(
            Dictionary<string, object> value,
            string label,
            HashSet<string> allowed,
            params string[] required)
        {
            foreach (string member in required)
                if (!value.ContainsKey(member))
                    throw Invalid(label + " is missing member '" + member + "'.");
            foreach (string member in value.Keys)
                if (!allowed.Contains(member))
                    throw Invalid(label + " contains unknown member '" + member + "'.");
        }

        private static Dictionary<string, object> RequiredObject(
            Dictionary<string, object> value,
            string key,
            string label)
        {
            object member;
            Dictionary<string, object> result;
            if (!value.TryGetValue(key, out member) ||
                (result = member as Dictionary<string, object>) == null)
                throw Invalid(label + " member '" + key + "' must be an object.");
            return result;
        }

        private static object[] RequiredArray(
            Dictionary<string, object> value,
            string key,
            string label)
        {
            object member;
            object[] result;
            if (!value.TryGetValue(key, out member) || (result = member as object[]) == null)
                throw Invalid(label + " member '" + key + "' must be an array.");
            return result;
        }

        private static string RequiredNonEmptyText(
            Dictionary<string, object> value,
            string key,
            string label)
        {
            string result = RequiredTextAllowEmpty(value, key, label);
            if (result.Length == 0)
                throw Invalid(label + " member '" + key + "' must not be empty.");
            return result;
        }

        private static string RequiredTextAllowEmpty(
            Dictionary<string, object> value,
            string key,
            string label)
        {
            object member;
            string result;
            if (!value.TryGetValue(key, out member) || (result = member as string) == null)
                throw Invalid(label + " member '" + key + "' must be a string.");
            return result;
        }

        private static string RequiredHex(
            Dictionary<string, object> value,
            string key,
            int length,
            string label)
        {
            string result = RequiredNonEmptyText(value, key, label);
            if (!IsLowerHex(result, length))
                throw Invalid(label + " member '" + key + "' is not canonical lowercase hexadecimal.");
            return result;
        }

        private static bool RequiredBoolean(
            Dictionary<string, object> value,
            string key,
            string label)
        {
            object member;
            if (!value.TryGetValue(key, out member) || !(member is bool))
                throw Invalid(label + " member '" + key + "' must be a boolean.");
            return (bool)member;
        }

        private static long RequiredNonNegativeInteger(
            Dictionary<string, object> value,
            string key,
            string label)
        {
            object member;
            if (!value.TryGetValue(key, out member))
                throw Invalid(label + " member '" + key + "' is missing.");
            long result;
            if (member is int) result = (int)member;
            else if (member is long) result = (long)member;
            else throw Invalid(label + " member '" + key + "' must be an integer.");
            if (result < 0) throw Invalid(label + " member '" + key + "' must be nonnegative.");
            return result;
        }

        private static void RequireText(
            Dictionary<string, object> value,
            string key,
            string expected,
            string label,
            bool allowEmpty = false)
        {
            string actual = allowEmpty
                ? RequiredTextAllowEmpty(value, key, label)
                : RequiredNonEmptyText(value, key, label);
            if (!String.Equals(actual, expected, StringComparison.Ordinal))
                throw Invalid(label + " member '" + key + "' does not match the package.");
        }

        private static void RequireBoolean(
            Dictionary<string, object> value,
            string key,
            bool expected,
            string label)
        {
            if (RequiredBoolean(value, key, label) != expected)
                throw Invalid(label + " member '" + key + "' does not match the package.");
        }

        private static void RequireInteger(
            Dictionary<string, object> value,
            string key,
            int expected,
            string label)
        {
            object member;
            if (!value.TryGetValue(key, out member) || !(member is int) || (int)member != expected)
                throw Invalid(label + " member '" + key + "' does not match the package.");
        }

        private static InvalidDataException Invalid(string message)
        {
            return new InvalidDataException(message);
        }

        private void ThrowIfDisposed()
        {
            if (disposed) throw new ObjectDisposedException("PackagedBackendIdentity");
        }

        private sealed class PackageExpectation
        {
            internal PackageExpectation(
                string sourceRevision,
                bool sourceDirty,
                string universalLauncherRevision,
                string universalSetupRevision,
                string backendSha256,
                long backendSize,
                string manifestSha256,
                string closureSha256)
            {
                SourceRevision = sourceRevision;
                SourceDirty = sourceDirty;
                UniversalLauncherRevision = universalLauncherRevision;
                UniversalSetupRevision = universalSetupRevision;
                BackendSha256 = backendSha256;
                BackendSize = backendSize;
                ManifestSha256 = manifestSha256;
                ClosureSha256 = closureSha256;
                ContractSetSha256 = String.Empty;
            }

            internal string SourceRevision { get; private set; }
            internal bool SourceDirty { get; private set; }
            internal string BuildIdentity
            {
                get
                {
                    return "facman=" + SourceRevision +
                        ";universal_launcher=" + UniversalLauncherRevision +
                        ";universal_setup=" + UniversalSetupRevision +
                        ";source_dirty=" + (SourceDirty ? "true" : "false");
                }
            }
            internal string UniversalLauncherRevision { get; private set; }
            internal string UniversalSetupRevision { get; private set; }
            internal string BackendSha256 { get; private set; }
            internal long BackendSize { get; private set; }
            internal string ManifestSha256 { get; private set; }
            internal string ClosureSha256 { get; private set; }
            internal string ContractSetSha256 { get; set; }
            internal int FilesVerified { get; set; }
        }

        private sealed class StablePath : IDisposable
        {
            private readonly string path;
            private readonly SafeFileHandle handle;
            private readonly FileIdentity identity;
            private readonly string finalNativePath;

            private StablePath(string openedPath, SafeFileHandle opened, bool directory)
            {
                path = openedPath;
                handle = opened;
                IsDirectory = directory;
                identity = Query(opened, directory);
                finalNativePath = directory
                    ? String.Empty
                    : FinalNativePathForHandle(opened);
            }

            internal bool IsDirectory { get; private set; }
            internal long Length { get { return identity.Length; } }
            internal string FinalNativePath { get { return finalNativePath; } }
            internal string GlobalRootPath { get { return @"\\?\GLOBALROOT" + finalNativePath; } }

            internal static StablePath Open(
                string path,
                bool directory,
                bool allowDeleteSharing = false)
            {
                SafeFileHandle handle = OpenHandle(path, directory, allowDeleteSharing);
                try
                {
                    StablePath result = new StablePath(path, handle, directory);
                    result.AllowDeleteSharing = allowDeleteSharing;
                    return result;
                }
                catch { handle.Dispose(); throw; }
            }

            private bool AllowDeleteSharing { get; set; }

            internal void Revalidate()
            {
                FileIdentity held = Query(handle, IsDirectory);
                if (!identity.Equals(held) || (!IsDirectory && !String.Equals(
                    finalNativePath,
                    FinalNativePathForHandle(handle),
                    StringComparison.OrdinalIgnoreCase)))
                    throw Invalid("A stable package path changed identity before process creation.");

                using (SafeFileHandle current = OpenHandle(
                    path, IsDirectory, AllowDeleteSharing))
                {
                    if (!identity.Equals(Query(current, IsDirectory)) ||
                        (!IsDirectory && !String.Equals(
                        finalNativePath,
                        FinalNativePathForHandle(current),
                        StringComparison.OrdinalIgnoreCase)))
                        throw Invalid(
                            "A package namespace path no longer resolves to its stable identity.");
                }
            }

            internal bool SameFile(StablePath other)
            {
                return other != null && !IsDirectory && !other.IsDirectory &&
                    identity.Equals(other.identity) && String.Equals(
                        finalNativePath, other.finalNativePath, StringComparison.OrdinalIgnoreCase);
            }

            public void Dispose()
            {
                handle.Dispose();
            }

            private static SafeFileHandle OpenHandle(
                string path,
                bool directory,
                bool allowDeleteSharing)
            {
                uint flags = FileFlagOpenReparsePoint |
                    (directory ? FileFlagBackupSemantics : 0u);
                uint shareMode = directory
                    ? FileShareRead | FileShareWrite |
                        (allowDeleteSharing ? FileShareDelete : 0u)
                    : FileShareRead;
                SafeFileHandle opened = CreateFile(
                    path,
                    directory ? 0u : GenericRead,
                    shareMode,
                    IntPtr.Zero,
                    OpenExisting,
                    flags,
                    IntPtr.Zero);
                if (opened.IsInvalid)
                {
                    int error = Marshal.GetLastWin32Error();
                    opened.Dispose();
                    throw new Win32Exception(
                        error,
                        "Cannot open stable package path (Windows error " +
                        error.ToString(CultureInfo.InvariantCulture) + "): " + path);
                }
                return opened;
            }

            private static string FinalNativePathForHandle(SafeFileHandle opened)
            {
                uint capacity = 1024;
                while (capacity <= 32768)
                {
                    StringBuilder buffer = new StringBuilder((int)capacity);
                    uint length = GetFinalPathNameByHandle(
                        opened, buffer, capacity, VolumeNameNt);
                    if (length == 0)
                        throw new Win32Exception(
                            Marshal.GetLastWin32Error(),
                            "Cannot query a stable package path's native identity.");
                    if (length < capacity) return buffer.ToString();
                    capacity = length + 1;
                }
                throw Invalid("A stable package native path exceeds the Windows path budget.");
            }

            private static FileIdentity Query(SafeFileHandle handle, bool directory)
            {
                ByHandleFileInformation info;
                if (!GetFileInformationByHandle(handle, out info))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                bool observedDirectory = (info.FileAttributes & FileAttributeDirectory) != 0;
                if ((info.FileAttributes & FileAttributeReparsePoint) != 0 ||
                    observedDirectory != directory)
                    throw Invalid("A package path is linked, reparse-backed, or changed type.");
                if (!directory && info.NumberOfLinks != 1)
                    throw Invalid("A package file is hard-linked outside its exact package identity.");
                long length = directory
                    ? 0
                    : ((long)info.FileSizeHigh << 32) | info.FileSizeLow;
                long writeTime = directory
                    ? 0
                    : ((long)info.LastWriteTimeHigh << 32) | info.LastWriteTimeLow;
                ulong fileIndex = ((ulong)info.FileIndexHigh << 32) | info.FileIndexLow;
                return new FileIdentity(
                    info.VolumeSerialNumber,
                    fileIndex,
                    length,
                    writeTime,
                    directory ? FileAttributeDirectory : info.FileAttributes,
                    directory ? 0u : info.NumberOfLinks);
            }
        }

        private struct FileIdentity
        {
            internal FileIdentity(
                uint volume,
                ulong index,
                long length,
                long writeTime,
                uint attributes,
                uint links)
            {
                Volume = volume;
                Index = index;
                Length = length;
                WriteTime = writeTime;
                Attributes = attributes;
                Links = links;
            }

            internal uint Volume;
            internal ulong Index;
            internal long Length;
            internal long WriteTime;
            internal uint Attributes;
            internal uint Links;

            public override bool Equals(object value)
            {
                if (!(value is FileIdentity)) return false;
                FileIdentity other = (FileIdentity)value;
                return Volume == other.Volume && Index == other.Index && Length == other.Length &&
                    WriteTime == other.WriteTime && Attributes == other.Attributes && Links == other.Links;
            }

            public override int GetHashCode()
            {
                return Volume.GetHashCode() ^ Index.GetHashCode() ^ Length.GetHashCode() ^
                    WriteTime.GetHashCode() ^ Attributes.GetHashCode() ^ Links.GetHashCode();
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct ByHandleFileInformation
        {
            internal uint FileAttributes;
            internal uint CreationTimeLow;
            internal uint CreationTimeHigh;
            internal uint LastAccessTimeLow;
            internal uint LastAccessTimeHigh;
            internal uint LastWriteTimeLow;
            internal uint LastWriteTimeHigh;
            internal uint VolumeSerialNumber;
            internal uint FileSizeHigh;
            internal uint FileSizeLow;
            internal uint NumberOfLinks;
            internal uint FileIndexHigh;
            internal uint FileIndexLow;
        }

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
        private static extern bool GetFileInformationByHandle(
            SafeFileHandle file,
            out ByHandleFileInformation information);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetFinalPathNameByHandle(
            SafeFileHandle file,
            StringBuilder filePath,
            uint filePathSize,
            uint flags);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool QueryFullProcessImageName(
            IntPtr process,
            uint flags,
            StringBuilder executableName,
            ref uint size);

        [DllImport("kernel32.dll")]
        private static extern IntPtr GetCurrentProcess();

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetModuleFileName(
            IntPtr module,
            StringBuilder fileName,
            int size);
    }
}
