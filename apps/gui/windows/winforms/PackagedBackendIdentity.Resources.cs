// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;

namespace FacMan.WinForms
{
    internal sealed partial class PackagedBackendIdentity
    {
        private static string ExpectedContractSet(
            string root, HashSet<string> actual, Dictionary<string, string> hashes,
            Dictionary<string, StablePath> paths, PackageExpectation expected)
        {
            if (expected.ProfileId == "windows_product_x64")
            {
                string declared;
                StablePath held;
                if (!actual.Contains("facman.resources") ||
                    !hashes.TryGetValue("facman.resources", out declared) ||
                    declared != expected.ResourceSha256 ||
                    !paths.TryGetValue(Path.GetFullPath(Path.Combine(root, "facman.resources")), out held) ||
                    held.IsDirectory || held.Length != expected.ResourceSize)
                    throw Invalid("The product resource component is not bound to the held package closure.");
                held.Revalidate();
                // This is the required digest, not frontend verification of packed
                // schemas. The mandatory product.inspect handshake must establish
                // native package verification and the digest of actual schema bytes.
                // The same held resource/backend leases span that handshake.
                return GeneratedCommandCatalog.ContractSetSha256;
            }
            string digest = ContractSetSha256(root, actual);
            if (digest != GeneratedCommandCatalog.ContractSetSha256)
                throw Invalid("The package contract set does not match the compiled frontend contract set.");
            return digest;
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

    }
}
