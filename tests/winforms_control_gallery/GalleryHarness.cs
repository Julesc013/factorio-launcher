// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Automation;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using FacMan.WinForms;

internal static class GalleryHarness
{
    private static int assertions;

    [STAThread]
    private static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.ThrowException);
        // Explicit construction must remain hermetic even with ordinary live mode selected.
        Environment.SetEnvironmentVariable("FACMAN_PRESENTATION_MODE", "live");
        if (args.Length == 2 && args[0] == "--show")
        {
            Application.Run(new C1ShellForm(C1GallerySession.Parse(File.ReadAllText(args[1]))));
            return 0;
        }
        if (args.Length != 3 || args[0] != "--check") return 2;
        string output = args[2];
        Directory.CreateDirectory(output);
        CheckFixtureRefusals(File.ReadAllText(Path.Combine(args[1], "ready.json")));
        var rows = new List<object>();
        foreach (string file in Directory.GetFiles(args[1], "*.json").OrderBy(value => value))
        {
            string fixture = File.ReadAllText(file);
            foreach (float scale in new[] { 1F, 1.25F, 1.5F, 2F })
                rows.Add(CheckCase(fixture, scale, output));
        }
        object constrained = CheckCase(File.ReadAllText(Path.Combine(args[1], "blocked.json")),
            1.25F, output, new Size(1024, 768));
        var report = new Dictionary<string, object> {
            { "schema", "facman.winforms_control_gallery.v1" },
            { "result", "PASS" }, { "assertions", assertions },
            { "live_transport_constructed", false }, { "rows", rows },
            { "constrained_rows", new[] { constrained } },
            { "actual_high_contrast", SystemInformation.HighContrast },
            { "scale_qualification", "Control.Scale fixture; actual monitor-DPI changes remain unqualified" },
            { "gtk", "pending" }, { "human_experience", "pending" }
        };
        File.WriteAllText(Path.Combine(output, "control-gallery.v1.json"),
            new JavaScriptSerializer().Serialize(report));
        Console.WriteLine("PASS: " + assertions + " production-control gallery assertions; " + rows.Count + " render cells");
        return 0;
    }

    private static object CheckCase(string fixture, float scale, string output, Size? maximumSize = null)
    {
        C1GallerySession session = C1GallerySession.Parse(fixture);
        Console.WriteLine("CELL " + session.ScenarioId + " scale=" + scale);
        C1Presentation original = session.Current;
        using (var form = new C1ShellForm(session))
        {
            Require(Field<object>(form, "liveStore") == null, "gallery must not construct a live store or transport");
            form.Show();
            form.Scale(new SizeF(scale, scale));
            form.Size = form.MinimumSize;
            if (maximumSize.HasValue)
            {
                form.MaximumSize = maximumSize.Value;
                form.Size = maximumSize.Value;
                Require(form.Width <= maximumSize.Value.Width && form.Height <= maximumSize.Value.Height,
                    "constrained window must use the requested bounds");
            }
            form.PerformLayout();
            Application.DoEvents();
            TabControl pages = Field<TabControl>(form, "pages");
            Require(pages.TabPages.Count == 7, "actual production pages must render");
            Require(AutomationElement.FromHandle(form.Handle).Current.ControlType == ControlType.Window,
                "native UIA window provider must exist");
            CheckState(form, session);
            var geometry = new List<object>();
            for (int page = 0; page < pages.TabCount; ++page)
            {
                pages.SelectedIndex = page;
                Application.DoEvents();
                foreach (Control control in Descendants(form).ToArray())
                {
                    if (!control.Visible || !control.Enabled || !control.TabStop ||
                        !(control is Button || control is ListView || control is TextBox || control is TabControl)) continue;
                    Require(!String.IsNullOrWhiteSpace(control.AccessibleName), "interactive control needs a name");
                    Require(control.Focus() && control.ContainsFocus, "keyboard focus enters " + control.AccessibleName);
                    Rectangle bounds = control.RectangleToScreen(control.ClientRectangle);
                    Rectangle visible = bounds;
                    for (Control parent = control.Parent; parent != null; parent = parent.Parent)
                        visible = Rectangle.Intersect(visible, parent.RectangleToScreen(parent.ClientRectangle));
                    Require(visible.Width >= Math.Min(16, bounds.Width) && visible.Height >= Math.Min(16, bounds.Height),
                        "control must remain reachable: " + control.AccessibleName +
                        "; scenario=" + session.ScenarioId + "; scale=" + scale +
                        "; form=" + form.Size + "; control=" + bounds + "; visible=" + visible);
                    geometry.Add(new { page = pages.SelectedTab.Text, name = control.AccessibleName,
                        width = bounds.Width, height = bounds.Height, visible_width = visible.Width, visible_height = visible.Height });
                }
                foreach (Button button in Descendants(form).OfType<Button>().Where(b => b.Visible && b.Enabled).ToArray())
                {
                    int before = session.Actions.Count;
                    button.PerformClick();
                    Application.DoEvents();
                    Require(session.Actions.Count == before + 1, "every gallery button records exactly once: " + button.AccessibleName);
                    Require(Application.OpenForms.Count == 1, "Advanced and actions cannot open a live child form");
                    Require(Object.ReferenceEquals(original, session.Current), "recorded actions cannot mutate the fixed scenario");
                }
            }
            var menu = form.MainMenuStrip.Items[1] as ToolStripMenuItem;
            int recorded = session.Actions.Count;
            menu.DropDownItems[0].PerformClick();
            Application.DoEvents();
            Require(session.Actions.Count == recorded + 1 && session.Actions.Last() == "presentation.refresh",
                "refresh menu also records without dispatching live transport");
            Require(session.Actions.Contains("advanced.open"), "Advanced action is exercised through the recorder");
            if (!session.ScenarioId.StartsWith("error/", StringComparison.Ordinal))
                Require(session.Actions.Contains("doctor.run"), "settings action is exercised through the recorder");
            Require(session.Actions.Contains("mods.inspect"), "descriptor action is exercised through the recorder");
            pages.SelectedIndex = 0;
            pages.SelectedTab.AutoScrollPosition = Point.Empty;
            Application.DoEvents();
            CheckPalette(form);
            string name = session.ScenarioId.Replace('/', '-') + "-" + (int)(scale * 100);
            if (maximumSize.HasValue)
                name += "-window-" + maximumSize.Value.Width + "x" + maximumSize.Value.Height;
            using (var bitmap = new Bitmap(form.Width, form.Height))
            {
                form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, form.Size));
                bitmap.Save(Path.Combine(output, name + ".png"));
            }
            var result = new { scenario = session.ScenarioId, scale = scale, actions = session.Actions.ToArray(),
                geometry = geometry, image = name + ".png", maximum_window = maximumSize };
            form.Close();
            return result;
        }
    }

    private static void CheckState(C1ShellForm form, C1GallerySession session)
    {
        string state = session.ScenarioId.Split('/')[0];
        C1Presentation view = session.Current;
        Require(view.SourceMode == "control_gallery" && view.AuthorityScope == "recording_only", "gallery authority must be explicit");
        if (state == "empty" || state == "error")
        {
            foreach (string list in new[] { "instancesList", "installationsList", "contentList", "savesList" })
                Require(Field<ListView>(form, list).Items.Count == 0, "empty/error must contain no sample rows: " + list);
            Require(Field<Label>(form, "deckInstance").Text.Contains("No instance selected"), "no sample selected identity");
            Require(!Field<Button>(form, "primaryAction").Visible, "missing backend action stays absent");
        }
        if (state == "ready") Require(view.Text("launch_deck", "primary_action", "availability") == "available", "ready Play action preserved");
        if (state == "blocked") Require(Field<TextBox>(form, "refusalDetail").Text.Contains("stale_readiness"), "blocked exact refusal displayed");
        if (state == "busy")
        {
            Require(Field<Label>(form, "deckStatus").Text.Contains("Running"), "active operation drives production status");
            Require(Field<ListView>(form, "activityList").Items.Count == 1, "busy operation identity displayed");
        }
        if (state == "recovery") Require(Field<Label>(form, "deckRefusal").Text.Contains("gallery-transaction"), "recovery identity displayed");
        if (state == "error") Require(view.Text("selected_instance", "readiness", "state") == "unavailable", "error cannot retain ready fixture data");
        if (session.ScenarioId.EndsWith("/overflow", StringComparison.Ordinal))
        {
            ListView list = Field<ListView>(form, "instancesList");
            Require(list.Items.Count == 41, "overflow has a real scrollable production list");
            list.EnsureVisible(40);
            Application.DoEvents();
            Require(list.ClientRectangle.Contains(list.Items[40].Bounds), "last overflow row is fully reachable by native scrolling");
            Label identity = Field<Label>(form, "deckInstance");
            Require(identity.Text.Contains("工場"), "Unicode identity remains exact");
            Require(identity.AutoEllipsis && identity.AccessibleDescription == identity.Text,
                "ellipsized identity remains available to accessibility clients");
            list.EnsureVisible(0);
        }
    }

    private static void CheckFixtureRefusals(string source)
    {
        foreach (string malformed in new[] {
            source.Replace("facman.control_gallery_case.v1", "unknown.schema"),
            source.Replace("\"ready\"", "\"unknown-state\""),
            source.Replace("2026-09-07T00:00:00Z", "2026-09-07T00:00:00"),
            source.Replace("\"launch_deck\"", "\"missing-scope\""),
            source.Replace("\"ready\"", "\"error\"") })
        {
            bool refused = false;
            try { C1GallerySession.Parse(malformed); }
            catch (InvalidDataException) { refused = true; }
            Require(refused, "invalid gallery input must fail before form construction");
        }
    }

    private static void CheckPalette(C1ShellForm form)
    {
        TextBox refusal = Field<TextBox>(form, "refusalDetail");
        Require(refusal.BackColor.ToArgb() == SystemColors.Info.ToArgb() &&
            refusal.ForeColor.ToArgb() == SystemColors.InfoText.ToArgb(), "production refusal follows native system palette");
        Require(Field<Label>(form, "deckRefusal").ForeColor.ToArgb() == SystemColors.ControlText.ToArgb(), "status follows native system text colour");
        Require(Contrast(SystemColors.ControlText, SystemColors.Control) >= 4.5, "observed native body-text contrast");
    }

    private static double Contrast(Color first, Color second)
    {
        Func<Color, double> luminance = c => .2126 * Linear(c.R) + .7152 * Linear(c.G) + .0722 * Linear(c.B);
        double a = luminance(first), b = luminance(second);
        return (Math.Max(a, b) + .05) / (Math.Min(a, b) + .05);
    }
    private static double Linear(byte value)
    {
        double v = value / 255.0;
        return v <= .04045 ? v / 12.92 : Math.Pow((v + .055) / 1.055, 2.4);
    }
    private static T Field<T>(object target, string name) where T : class
    {
        return typeof(C1ShellForm).GetField(name, BindingFlags.NonPublic | BindingFlags.Instance).GetValue(target) as T;
    }
    private static IEnumerable<Control> Descendants(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            yield return child;
            foreach (Control descendant in Descendants(child)) yield return descendant;
        }
    }
    private static void Require(bool condition, string message)
    {
        ++assertions;
        if (!condition) throw new InvalidOperationException(message);
    }
}
