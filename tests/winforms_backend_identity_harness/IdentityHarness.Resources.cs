// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

internal static partial class IdentityHarness
{
    private static void CheckProductionRpc(Assembly frontend, object lease, string work)
    {
        Func<string, Type> type = name => frontend.GetType("FacMan.WinForms." + name, true);
        BindingFlags flags = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static;
        object command = Invoke(type("GeneratedCommandCatalog").GetMethod("Find", flags), null, "product.inspect");
        object identity = Invoke(type("TransportIdentity").GetMethod("Create", flags), null);
        object client = Activator.CreateInstance(type("CliProcessClient"));
        MethodInfo core = type("CliProcessClient").GetMethod("InvokeCoreAsync",
            BindingFlags.NonPublic | BindingFlags.Instance);
        Task task = (Task)Invoke(core, client, command, new Dictionary<string, object>(),
            Path.Combine(work, "rpc-workspace"), identity, lease, false,
            DateTime.UtcNow.AddSeconds(30), CancellationToken.None);
        Require(task.Wait(40000), "production contained RPC did not settle");
        object result = task.GetType().GetProperty("Result").GetValue(task, null);
        Require((bool)result.GetType().GetProperty("Success").GetValue(result, null),
            "production contained RPC failed: " +
            result.GetType().GetProperty("RefusalReason").GetValue(result, null));
        MethodInfo validate = lease.GetType().GetMethod("ValidateHandshake",
            BindingFlags.NonPublic | BindingFlags.Instance);
        Invoke(validate, lease, result);
        string handshake = (string)result.GetType().GetProperty("Stdout").GetValue(result, null);
        MethodInfo factory = type("CommandResult").GetMethod("ValidatedTerminal", flags);
        foreach (string member in new[] { "verified", "build_matches_package", "contract_set_matches_build" })
            RequireHandshakeMutationRefused(validate, factory, lease, handshake,
                "\"" + member + "\":true", "\"" + member + "\":false", member);
    }

    private static void CheckHeldResource(string root)
    {
        string path = Path.Combine(root, "facman.resources");
        if (!File.Exists(path)) return; // Legacy loose-schema package.
        bool denied = false;
        try { File.WriteAllText(path, "replacement"); }
        catch (IOException) { denied = true; }
        catch (UnauthorizedAccessException) { denied = true; }
        Require(denied, "the held product resource pack allowed replacement");
    }

    private static void CheckResourceMutations(
        string source, string work, string moduleRelative, MethodInfo open)
    {
        if (!File.Exists(Path.Combine(source, "facman.resources"))) return;
        foreach (string kind in new[] { "pack_bytes", "component_size", "component_target" })
        {
            string root = Path.Combine(work, "resource-" + kind);
            CopyTree(source, root);
            if (kind == "pack_bytes")
                File.WriteAllText(Path.Combine(root, "facman.resources"), "changed pack");
            else
            {
                string path = Path.Combine(root, "manifest", "components.v1.json");
                var json = new JavaScriptSerializer { MaxJsonLength = 1048576 };
                var document = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path));
                bool changed = false;
                foreach (object item in (System.Collections.IEnumerable)document["components"])
                {
                    var component = (Dictionary<string, object>)item;
                    if ((string)component["name"] != "runtime_resources") continue;
                    if (kind == "component_size") component["size"] = 1;
                    else component["source_target"] = "foreign.resources";
                    changed = true;
                }
                Require(changed, "resource component mutation did not find its target");
                File.WriteAllText(path, json.Serialize(document), new System.Text.UTF8Encoding(false));
                // Keep the outer hash closure coherent so this probes component
                // semantics against actual held pack bytes, not a stale JSON hash.
                string hashes = Path.Combine(root, "manifest", "hashes.sha256");
                string[] rows = File.ReadAllLines(hashes);
                using (var sha = SHA256.Create())
                {
                    string digest = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path)))
                        .Replace("-", "").ToLowerInvariant();
                    for (int i = 0; i < rows.Length; i++)
                        if (rows[i].EndsWith("  manifest/components.v1.json", StringComparison.Ordinal))
                            rows[i] = digest + "  manifest/components.v1.json";
                }
                File.WriteAllLines(hashes, rows, new System.Text.UTF8Encoding(false));
            }
            bool refused = false;
            try { ((IDisposable)Invoke(open, null, root, Path.Combine(root, moduleRelative))).Dispose(); }
            catch (InvalidDataException) { refused = true; }
            Require(refused, "resource mutation was accepted: " + kind);
        }
    }
}
