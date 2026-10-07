// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Reflection;
using System.Threading;
using FacMan.WinForms;

// Headless compiled product-state checks; never opens a form or dispatches a process.
internal static class ObservationIntentHarness
{
    private static int Main()
    {
        try
        {
            var store = new C1LivePresentationStore();
            Require(store.ObservationIntent == "menu", "default observation must be Menu");
            typeof(C1LivePresentationStore).GetProperty("Busy").GetSetMethod(true).Invoke(store, new object[] { true });
            Require(!store.SelectObservationIntentAsync("load_save", CancellationToken.None).Result,
                "pending refresh must reject a selector change");
            Require(store.ObservationIntent == "menu", "rejected selector must preserve accepted context");
            var refused = store.ExecuteDescriptorActionAsync("launch_deck", "launch.play",
                new Dictionary<string, object>(), CancellationToken.None).Result;
            Require(!refused.Success && refused.RefusalCode == "presentation_snapshot_unavailable",
                "pending refresh must block snapshot actions");
            var pendingType = typeof(C1LivePresentationStore).GetNestedType("PendingSemanticAction", BindingFlags.NonPublic);
            var payload = new Dictionary<string, object> {
                { "launch_intent", "load_save" }, { "expected_snapshot_revision", new string('a', 64) },
                { "idempotency_key", "original-key" }
            };
            Type identityType = typeof(C1LivePresentationStore).Assembly.GetType("FacMan.WinForms.TransportIdentity");
            object identity = identityType.GetMethod("Create", BindingFlags.Static | BindingFlags.NonPublic)
                .Invoke(null, null);
            object pending = Activator.CreateInstance(pendingType, BindingFlags.Instance | BindingFlags.NonPublic,
                null, new object[] { "launch_deck", "launch.play", payload, identity, false }, null);
            typeof(C1LivePresentationStore).GetField("uncertainAction", BindingFlags.Instance | BindingFlags.NonPublic)
                .SetValue(store, pending);
            payload["launch_intent"] = "menu";
            typeof(C1LivePresentationStore).GetProperty("ObservationIntent").GetSetMethod(true)
                .Invoke(store, new object[] { "menu" });
            var retained = (IDictionary<string, object>)pendingType.GetProperty("Payload",
                BindingFlags.Instance | BindingFlags.NonPublic).GetValue(pending, null);
            Require((string)retained["launch_intent"] == "load_save" &&
                (string)retained["idempotency_key"] == "original-key", "uncertain replay changed original input");
            Require(Object.ReferenceEquals(identity, pendingType.GetProperty("Identity",
                BindingFlags.Instance | BindingFlags.NonPublic).GetValue(pending, null)), "uncertain identity changed");
            Require(store.HasUncertainAction, "changing observation erased uncertainty");
            var previewInput = new Dictionary<string, object> {
                { "composition_state", "partial" }, { "plan_digest", new string('b', 64) },
                // Even malformed incoming authority booleans cannot enable an advisory apply.
                { "preparation_available", true },
                { "installation", new Dictionary<string, object> {
                    { "disposition", "plan" }, { "refusal", null },
                    { "report", new Dictionary<string, object> { { "plan_digest", new string('c', 64) } } }
                } },
                { "profile", new Dictionary<string, object> {
                    { "disposition", "refusal" }, { "report", null }, { "refusal", "profile_overrides_invalid" }
                } }
            };
            var readiness = (PresentationReadiness)Activator.CreateInstance(typeof(PresentationReadiness),
                BindingFlags.Instance | BindingFlags.NonPublic, null,
                new object[] { new Dictionary<string, object> {
                    { "execution_available", false }, { "preparation_preview", previewInput }
                } }, null);
            Require(!readiness.Available && !readiness.PreparationApplyAvailable,
                "preview granted preparation or execution authority");
            Require(readiness.PreparationPreviewState == "partial" &&
                readiness.PreparationPreviewDigest == new string('b', 64) &&
                readiness.PreparationInstallationPlanDigest == new string('c', 64), "preview identities lost");
            Require(readiness.PreparationOwnerSummaries.Count == 2 &&
                readiness.PreparationOwnerSummaries[1].Contains("profile_overrides_invalid") &&
                !readiness.PreparationOwnerSummaries[0].Contains(new string('c', 64)), "advisory owner summaries invalid");
            var backendInput = new Dictionary<string, object> {
                { "schema", "facman.presentation_snapshot.v1" }, { "revision", new string('d', 64) },
                { "readiness", new Dictionary<string, object> {
                    { "overall_state", "blocked" }, { "execution_available", false }, { "preparation_preview", previewInput }
                } }
            };
            var backend = (BackendPresentationSnapshot)typeof(BackendPresentationSnapshot).GetMethod("ParseRecord",
                BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, new object[] { backendInput });
            Type projectionType = typeof(BackendPresentationSnapshot).Assembly.GetType("FacMan.WinForms.C1SnapshotProjection");
            MethodInfo readinessRecord = projectionType.GetMethod("ReadinessRecord",
                BindingFlags.NonPublic | BindingFlags.Static);
            var advisory = (IDictionary<string, object>)readinessRecord.Invoke(null,
                new object[] { backend, new DateTime(2026, 10, 7, 0, 0, 0, DateTimeKind.Utc) });
            Require(((string)advisory["summary"]).Contains("Preparation preview: partial; apply unavailable") &&
                !((string)advisory["summary"]).Contains(new string('c', 64)), "Launch Deck advisory missing");
            Console.WriteLine("PASS default Menu, busy selector refusal, pending action refusal, immutable uncertain intent and identity; advisory preview and unavailable apply");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
