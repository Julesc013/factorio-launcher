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
            Console.WriteLine("PASS default Menu, busy selector refusal, pending action refusal, immutable uncertain intent and identity");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
