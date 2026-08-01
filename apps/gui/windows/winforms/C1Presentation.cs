// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;

namespace FacMan.WinForms
{
    /// <summary>
    /// FacMan-local adapter for the toolkit-neutral facman.presentation.v0 record.
    /// The public contract remains JSON; this class deliberately exposes no
    /// Windows Forms types and is not a Universal Launcher ABI.
    /// </summary>
    public sealed class C1Presentation
    {
        private readonly IDictionary<string, object> root;

        private C1Presentation(IDictionary<string, object> root)
        {
            this.root = root;
        }

        public string Contract { get { return Text("contract"); } }
        public string FixtureState { get { return Text("fixture_state"); } }
        public string AuthorityScope { get { return Text("authority_scope"); } }
        public string SourceMode
        {
            get
            {
                string mode = Text("source_mode");
                return String.IsNullOrWhiteSpace(mode) ? "evidence_fixture" : mode;
            }
        }

        public string Text(params string[] path)
        {
            object value = Value(path);
            return value == null ? String.Empty : Convert.ToString(value);
        }

        public int Number(params string[] path)
        {
            object value = Value(path);
            return value == null ? 0 : Convert.ToInt32(value);
        }

        public bool Has(params string[] path)
        {
            return Value(path) != null;
        }

        public IDictionary<string, object> Record(params string[] path)
        {
            return Value(path) as IDictionary<string, object>;
        }

        public IList<object> Records(params string[] path)
        {
            object[] values = Value(path) as object[];
            if (values != null) return Array.AsReadOnly(values);
            IList<object> list = Value(path) as IList<object>;
            return list == null ? new List<object>().AsReadOnly() : new List<object>(list).AsReadOnly();
        }

        private object Value(params string[] path)
        {
            object current = root;
            foreach (string segment in path)
            {
                IDictionary<string, object> record = current as IDictionary<string, object>;
                object next;
                if (record == null || !record.TryGetValue(segment, out next)) return null;
                current = next;
            }
            return current;
        }

        public static C1Presentation Parse(string json)
        {
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength = 1024 * 1024;
            IDictionary<string, object> record = serializer.DeserializeObject(json) as IDictionary<string, object>;
            if (record == null) throw new InvalidDataException("Presentation fixture root must be an object.");
            C1Presentation presentation = new C1Presentation(record);
            if (presentation.Contract != "facman.presentation.v0")
                throw new InvalidDataException("Unsupported presentation contract: " + presentation.Contract);
            return presentation;
        }

        internal IDictionary<string, object> CloneRecord()
        {
            JavaScriptSerializer serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength = 1024 * 1024;
            return serializer.DeserializeObject(serializer.Serialize(root)) as IDictionary<string, object>;
        }

        internal static C1Presentation FromRecord(IDictionary<string, object> record)
        {
            if (record == null) throw new ArgumentNullException("record");
            return new C1Presentation(record);
        }
    }

    public sealed class C1FixturePresentationStore
    {
        private static readonly string[] StateOrder =
            { "positive", "refused", "running", "exited", "interrupted" };
        private readonly IDictionary<string, C1Presentation> presentations;

        public C1FixturePresentationStore()
        {
            presentations = new Dictionary<string, C1Presentation>(StringComparer.Ordinal);
            foreach (string state in StateOrder)
                presentations[state] = LoadEmbedded(state);
            Current = presentations["positive"];
        }

        public C1Presentation Current { get; private set; }

        public IList<string> States
        {
            get { return Array.AsReadOnly(StateOrder); }
        }

        public C1Presentation Select(string state)
        {
            C1Presentation presentation;
            if (!presentations.TryGetValue(state, out presentation))
                throw new ArgumentOutOfRangeException("state", state, "Unknown deterministic fixture state.");
            Current = presentation;
            return Current;
        }

        public C1Presentation Apply(string actionId)
        {
            if (actionId == "instance.play")
            {
                if (Current.FixtureState == "refused") return Current;
                if (Current.FixtureState == "positive" || Current.FixtureState == "exited")
                    return Select("running");
            }
            if (actionId == "instance.readiness.refresh" && Current.FixtureState == "refused")
                return Select("positive");
            if (actionId == "recovery.apply" && Current.FixtureState == "interrupted")
                return Select("positive");
            return Current;
        }

        private static C1Presentation LoadEmbedded(string state)
        {
            string name = "FacMan.WinForms.Fixtures." + state + ".json";
            Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name);
            if (stream == null) throw new InvalidDataException("Missing embedded presentation fixture: " + name);
            using (stream)
            using (StreamReader reader = new StreamReader(stream, Encoding.UTF8, true))
                return C1Presentation.Parse(reader.ReadToEnd());
        }
    }
}
