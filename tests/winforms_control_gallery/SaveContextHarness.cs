// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using FacMan.WinForms;

internal static class SaveContextHarness
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            var serializer = new JavaScriptSerializer { MaxJsonLength = 1024 * 1024 };
            var input = serializer.DeserializeObject(File.ReadAllText(args[0])) as IDictionary<string, object>;
            foreach (object value in (object[])input["cases"])
            {
                var test = (IDictionary<string, object>)value;
                var expected = (IDictionary<string, object>)test["expected"];
                string name = Convert.ToString(test["name"]);
                var gallery = C1GallerySession.Parse(serializer.Serialize(test["gallery"]));
                var items = gallery.Current.Records("pages", "saves", "items");
                Require(items.Count == 1, name + ": exact selected save required");
                var item = (IDictionary<string, object>)items[0];
                foreach (string field in new[] { "association_status", "association_context_status",
                    "association_version_status", "association_modset_status" })
                    Require(Text(item, field) == Text(expected, field), name + ": owner observation lost: " + field);

                using (var form = new C1ShellForm(gallery))
                {
                    form.CreateControl();
                    var list = (ListView)typeof(C1ShellForm).GetField("savesList",
                        BindingFlags.Instance | BindingFlags.NonPublic).GetValue(form);
                    Require(list.Items.Count == 1, name + ": save row missing");
                    int bytes = Column(list, "Save bytes");
                    int context = Column(list, "Declared context");
                    Require(bytes >= 0 && context >= 0 && bytes != context, name + ": distinct byte/context columns required");
                    Require(list.Items[0].SubItems[bytes].Text == Text(expected, "association_status"), name + ": save-byte outcome changed");
                    string rendered = list.Items[0].SubItems[context].Text;
                    if (Text(expected, "association_context_status") == String.Empty)
                        Require(rendered == "Not observed", name + ": absent context must remain unobserved");
                    else
                    {
                        Require(rendered.StartsWith(Text(expected, "association_context_status"), StringComparison.Ordinal), name + ": overall owner state missing");
                        Require(rendered.Contains("version " + Text(expected, "association_version_status")), name + ": version state missing");
                        Require(rendered.Contains("content " + Text(expected, "association_modset_status")), name + ": content state missing");
                    }
                    Require(list.AccessibleDescription.Contains("declared"), name + ": declared observation scope missing");
                }
                Require(gallery.Actions.Count == 0, name + ": observation caused an action");
                Console.WriteLine("PASS " + name + ": bytes=" + Text(expected, "association_status") +
                    ", context=" + Text(expected, "association_context_status"));
            }
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            return 1;
        }
    }

    private static string Text(IDictionary<string, object> record, string key)
    {
        object value;
        return record.TryGetValue(key, out value) && value != null ? Convert.ToString(value) : String.Empty;
    }

    private static int Column(ListView list, string title)
    {
        for (int index = 0; index < list.Columns.Count; ++index)
            if (list.Columns[index].Text == title) return index;
        return -1;
    }

    private static void Require(bool condition, string detail)
    {
        if (!condition) throw new InvalidOperationException(detail);
    }
}
