// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
    /// <summary>A fixed production projection and an in-memory action recorder.</summary>
    public sealed class C1GallerySession
    {
        private readonly List<string> actions = new List<string>();

        private C1GallerySession() { }

        public string ScenarioId { get; private set; }
        public C1Presentation Current { get; private set; }
        public IList<string> Actions { get { return actions.AsReadOnly(); } }

        public static C1GallerySession Parse(string json)
        {
            var serializer = new JavaScriptSerializer { MaxJsonLength = 1024 * 1024 };
            var fixture = serializer.DeserializeObject(json) as IDictionary<string, object>;
            if (fixture == null || PresentationJson.Text(fixture, "schema") != "facman.control_gallery_case.v1")
                throw new InvalidDataException("Unsupported control gallery fixture.");
            string state = PresentationJson.Text(fixture, "state");
            if (Array.IndexOf(new[] { "ready", "blocked", "busy", "recovery", "empty", "error" }, state) < 0)
                throw new InvalidDataException("Unknown control gallery state.");
            DateTime observed;
            if (!DateTime.TryParse(PresentationJson.Text(fixture, "observed_at"),
                CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out observed) ||
                observed.Kind != DateTimeKind.Utc)
                throw new InvalidDataException("Gallery fixture needs an explicit UTC observation time.");
            var snapshots = new Dictionary<string, BackendPresentationSnapshot>(StringComparer.Ordinal);
            var records = PresentationJson.Record(fixture, "snapshots");
            foreach (string scope in new[] { "launch_deck", "instances", "installations",
                "content", "saves", "activity_recovery", "settings_support" })
            {
                var record = PresentationJson.Record(records, scope);
                if (state == "error")
                {
                    if (record != null) throw new InvalidDataException("Error fixture must not contain stale snapshots.");
                    continue;
                }
                var snapshot = BackendPresentationSnapshot.ParseRecord(record);
                if (snapshot == null || snapshot.Page.Scope != scope)
                    throw new InvalidDataException("Missing or mismatched gallery scope: " + scope);
                snapshots[scope] = snapshot;
            }
            var session = new C1GallerySession();
            session.ScenarioId = state + "/" + PresentationJson.Text(fixture, "variant");
            session.Current = state == "error"
                ? C1SnapshotProjection.BuildUnavailable(PresentationJson.Text(fixture, "error"))
                : C1SnapshotProjection.Build(snapshots, null, observed);
            var view = session.Current.CloneRecord();
            view["source_mode"] = "control_gallery";
            view["authority_scope"] = "recording_only";
            session.Current = C1Presentation.FromRecord(view);
            return session;
        }

        internal void RecordAction(string actionId)
        {
            // This is intentionally the entire gallery action boundary. No
            // callback, transport, process or filesystem effect is available.
            actions.Add(actionId ?? String.Empty);
        }
    }
}
