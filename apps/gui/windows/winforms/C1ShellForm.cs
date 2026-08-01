// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;

namespace FacMan.WinForms
{
    /// <summary>
    /// Windows 10/11 x64 reference presentation for the deterministic C1
    /// journey. Backend behavior stays in FacMan; this form renders the
    /// FacMan-local presentation record and never starts Factorio directly.
    /// </summary>
    public sealed class C1ShellForm : Form
    {
        private readonly C1FixturePresentationStore presentationStore;
        private readonly ToolTip toolTip;
        private TabControl pages;
        private ListView instancesList;
        private Label instancesSummary;
        private Label readinessSummary;
        private TextBox refusalDetail;
        private Label installationsSummary;
        private ListView installationsList;
        private Label activitySummary;
        private ListView activityList;
        private FlowLayoutPanel activityActions;
        private ComboBox evidenceState;
        private Label evidenceScope;
        private Label deckInstance;
        private Label deckStatus;
        private Label deckReadiness;
        private Label deckLastRun;
        private Label deckRefusal;
        private Button primaryAction;
        private Button secondaryAction;
        private ToolStripStatusLabel statusLabel;
        private bool rendering;

        public C1ShellForm()
        {
            presentationStore = new C1FixturePresentationStore();
            toolTip = new ToolTip();

            Text = "FacMan";
            ClientSize = new Size(1040, 720);
            MinimumSize = new Size(960, 640);
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleDimensions = new SizeF(96F, 96F);
            AutoScaleMode = AutoScaleMode.Dpi;
            Font = SystemFonts.MessageBoxFont;
            AccessibleName = "FacMan C1 product window";
            AccessibleDescription =
                "Instances, Installations, Activity, Settings and About, a persistent Launch Deck, and Advanced commands.";
            KeyPreview = true;

            BuildLayout();
            RenderPresentation();
        }

        private void BuildLayout()
        {
            TableLayoutPanel root = new TableLayoutPanel();
            root.Dock = DockStyle.Fill;
            root.ColumnCount = 1;
            root.RowCount = 4;
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            Controls.Add(root);

            MenuStrip menu = BuildMenu();
            MainMenuStrip = menu;
            root.Controls.Add(menu, 0, 0);

            pages = new TabControl();
            pages.Dock = DockStyle.Fill;
            pages.AccessibleName = "FacMan product pages";
            pages.AccessibleDescription = "Four player-facing pages followed by the Advanced command explorer entry.";
            root.Controls.Add(pages, 0, 1);

            pages.TabPages.Add(BuildInstancesPage());
            pages.TabPages.Add(BuildInstallationsPage());
            pages.TabPages.Add(BuildActivityPage());
            pages.TabPages.Add(BuildSettingsPage());
            pages.TabPages.Add(BuildAdvancedPage());

            root.Controls.Add(BuildLaunchDeck(), 0, 2);

            StatusStrip status = new StatusStrip();
            statusLabel = new ToolStripStatusLabel("Ready");
            statusLabel.AccessibleName = "FacMan status announcement";
            status.Items.Add(statusLabel);
            root.Controls.Add(status, 0, 3);
        }

        private MenuStrip BuildMenu()
        {
            MenuStrip menu = new MenuStrip();
            ToolStripMenuItem navigate = new ToolStripMenuItem("&Navigate");
            navigate.DropDownItems.Add(NavigationItem("&Instances", Keys.Control | Keys.D1, 0));
            navigate.DropDownItems.Add(NavigationItem("Insta&llations", Keys.Control | Keys.D2, 1));
            navigate.DropDownItems.Add(NavigationItem("&Activity", Keys.Control | Keys.D3, 2));
            navigate.DropDownItems.Add(NavigationItem("&Settings / About", Keys.Control | Keys.D4, 3));
            navigate.DropDownItems.Add(new ToolStripSeparator());
            navigate.DropDownItems.Add(NavigationItem("A&dvanced", Keys.Control | Keys.D5, 4));
            menu.Items.Add(navigate);

            ToolStripMenuItem evidence = new ToolStripMenuItem("&Evidence");
            evidence.DropDownItems.Add(EvidenceItem("&Ready", "positive"));
            evidence.DropDownItems.Add(EvidenceItem("Stale &readiness", "refused"));
            evidence.DropDownItems.Add(EvidenceItem("R&unning", "running"));
            evidence.DropDownItems.Add(EvidenceItem("E&xited / Last Run", "exited"));
            evidence.DropDownItems.Add(EvidenceItem("&Interrupted / recovery", "interrupted"));
            menu.Items.Add(evidence);
            menu.AccessibleName = "FacMan application menu";
            return menu;
        }

        private ToolStripMenuItem NavigationItem(string text, Keys shortcut, int pageIndex)
        {
            ToolStripMenuItem item = new ToolStripMenuItem(text);
            item.ShortcutKeys = shortcut;
            item.ShowShortcutKeys = true;
            item.Click += delegate { pages.SelectedIndex = pageIndex; pages.Focus(); };
            return item;
        }

        private ToolStripMenuItem EvidenceItem(string text, string state)
        {
            ToolStripMenuItem item = new ToolStripMenuItem(text);
            item.Tag = state;
            item.Click += delegate { SelectEvidenceState(state); };
            return item;
        }

        private TabPage BuildInstancesPage()
        {
            TabPage page = Page("Instances", "Instances page");
            TableLayoutPanel layout = PageLayout(5);
            page.Controls.Add(layout);

            layout.Controls.Add(Heading("Instances", "Choose an isolated instance and check readiness before Play."), 0, 0);
            instancesSummary = BodyLabel("Instances summary");
            layout.Controls.Add(instancesSummary, 0, 1);

            instancesList = new ListView();
            instancesList.Dock = DockStyle.Fill;
            instancesList.View = View.Details;
            instancesList.FullRowSelect = true;
            instancesList.HideSelection = false;
            instancesList.MultiSelect = false;
            instancesList.AccessibleName = "Instances";
            instancesList.AccessibleDescription = "Available isolated Factorio instances and their readiness state.";
            instancesList.Columns.Add("Name", 220);
            instancesList.Columns.Add("Readiness", 130);
            instancesList.Columns.Add("Journey state", 150);
            instancesList.Columns.Add("Installation", 360);
            layout.Controls.Add(instancesList, 0, 2);

            readinessSummary = BodyLabel("Selected instance readiness");
            readinessSummary.BorderStyle = BorderStyle.FixedSingle;
            readinessSummary.Padding = new Padding(8);
            layout.Controls.Add(readinessSummary, 0, 3);

            TableLayoutPanel actions = new TableLayoutPanel();
            actions.AutoSize = true;
            actions.Dock = DockStyle.Fill;
            actions.ColumnCount = 3;
            actions.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            actions.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            Button create = ActionButton("&Create instance", "Create instance", "instance.create");
            Button rescan = ActionButton("&Rescan readiness", "Rescan readiness", "instance.readiness.refresh");
            actions.Controls.Add(create, 0, 0);
            actions.Controls.Add(rescan, 1, 0);
            refusalDetail = new TextBox();
            refusalDetail.Multiline = true;
            refusalDetail.ReadOnly = true;
            refusalDetail.Dock = DockStyle.Fill;
            refusalDetail.Height = 62;
            refusalDetail.BackColor = SystemColors.Info;
            refusalDetail.ForeColor = SystemColors.InfoText;
            refusalDetail.AccessibleName = "Structured Play refusal";
            refusalDetail.AccessibleDescription = "Exact refusal code, readiness revisions, explanation, and safe action.";
            actions.Controls.Add(refusalDetail, 2, 0);
            layout.Controls.Add(actions, 0, 4);
            return page;
        }

        private TabPage BuildInstallationsPage()
        {
            TabPage page = Page("Installations", "Installations page");
            TableLayoutPanel layout = PageLayout(4);
            page.Controls.Add(layout);
            layout.Controls.Add(Heading("Installations", "Inspect existing Factorio installations without repairing or updating them."), 0, 0);
            installationsSummary = BodyLabel("Installations summary");
            layout.Controls.Add(installationsSummary, 0, 1);
            installationsList = new ListView();
            installationsList.Dock = DockStyle.Fill;
            installationsList.View = View.Details;
            installationsList.FullRowSelect = true;
            installationsList.AccessibleName = "Detected installations";
            installationsList.Columns.Add("Installation", 390);
            installationsList.Columns.Add("Kind", 150);
            installationsList.Columns.Add("Version", 140);
            layout.Controls.Add(installationsList, 0, 2);
            FlowLayoutPanel actions = ActionRow();
            actions.Controls.Add(ActionButton("&Scan for installations", "Scan for installations", "installation.scan"));
            layout.Controls.Add(actions, 0, 3);
            return page;
        }

        private TabPage BuildActivityPage()
        {
            TabPage page = Page("Activity", "Activity page");
            TableLayoutPanel layout = PageLayout(4);
            page.Controls.Add(layout);
            layout.Controls.Add(Heading("Activity", "Observe backend-owned operations, ordinary exits, and recovery state."), 0, 0);
            activitySummary = BodyLabel("Activity summary");
            layout.Controls.Add(activitySummary, 0, 1);
            activityList = new ListView();
            activityList.Dock = DockStyle.Fill;
            activityList.View = View.Details;
            activityList.FullRowSelect = true;
            activityList.AccessibleName = "Operation activity";
            activityList.AccessibleDescription = "Running, exited, or interrupted backend operation records.";
            activityList.Columns.Add("Operation", 220);
            activityList.Columns.Add("Status", 120);
            activityList.Columns.Add("Progress", 120);
            activityList.Columns.Add("Summary", 430);
            layout.Controls.Add(activityList, 0, 2);
            activityActions = ActionRow();
            activityActions.AccessibleName = "Recovery actions";
            layout.Controls.Add(activityActions, 0, 3);
            return page;
        }

        private TabPage BuildSettingsPage()
        {
            TabPage page = Page("Settings / About", "Settings and About page");
            TableLayoutPanel layout = PageLayout(5);
            page.Controls.Add(layout);
            layout.Controls.Add(Heading("Settings / About", "System Native appearance and bounded C1 reference-lane information."), 0, 0);

            Label about = BodyLabel("About FacMan C1");
            about.Text =
                "FacMan C1 reference shell | Windows 10/11 x64 | .NET Framework 4.8\r\n" +
                "Appearance: System Native. Layout: Per-Monitor V2 DPI-aware at 100%, 150%, and 200%.\r\n" +
                "Transport: bounded process RPC. Advanced commands remain a thin client of the FacMan backend.";
            layout.Controls.Add(about, 0, 1);

            evidenceScope = BodyLabel("Presentation authority scope");
            evidenceScope.BorderStyle = BorderStyle.FixedSingle;
            evidenceScope.Padding = new Padding(8);
            layout.Controls.Add(evidenceScope, 0, 2);

            FlowLayoutPanel chooser = ActionRow();
            Label chooserLabel = new Label();
            chooserLabel.Text = "&Deterministic evidence state:";
            chooserLabel.AutoSize = true;
            chooserLabel.Padding = new Padding(0, 8, 4, 0);
            evidenceState = new ComboBox();
            evidenceState.DropDownStyle = ComboBoxStyle.DropDownList;
            evidenceState.Width = 220;
            evidenceState.AccessibleName = "Deterministic evidence state";
            evidenceState.AccessibleDescription =
                "Selects one embedded fixture for presentation review; it is not a live product action.";
            foreach (string state in presentationStore.States) evidenceState.Items.Add(state);
            chooserLabel.Click += delegate { evidenceState.Focus(); };
            evidenceState.SelectedIndexChanged += delegate
            {
                if (!rendering && evidenceState.SelectedItem != null)
                    SelectEvidenceState(Convert.ToString(evidenceState.SelectedItem));
            };
            chooser.Controls.Add(chooserLabel);
            chooser.Controls.Add(evidenceState);
            layout.Controls.Add(chooser, 0, 3);

            Label boundary = BodyLabel("C1 authority boundary");
            boundary.Text =
                "The embedded journey starts no live Factorio process and grants no route, permit, verdict, " +
                "promotion, publication, daemon, direct-client, transport-rewrite, or Universal Launcher ABI authority.";
            layout.Controls.Add(boundary, 0, 4);
            return page;
        }

        private TabPage BuildAdvancedPage()
        {
            TabPage page = Page("Advanced", "Advanced page");
            TableLayoutPanel layout = PageLayout(3);
            page.Controls.Add(layout);
            layout.Controls.Add(Heading("Advanced", "Open the generated command explorer for exhaustive backend commands and diagnostics."), 0, 0);
            Label explanation = BodyLabel("Generated command explorer boundary");
            explanation.Text =
                "The generated explorer is retained here for command/result/refusal parity. It is not the product home, " +
                "does not reinterpret backend state, and uses the existing bounded process RPC client.";
            layout.Controls.Add(explanation, 0, 1);
            FlowLayoutPanel actions = ActionRow();
            Button open = new Button();
            open.Text = "&Open command explorer";
            open.AutoSize = true;
            open.MinimumSize = new Size(190, 36);
            open.AccessibleName = "Open generated command explorer";
            open.AccessibleDescription = "Opens generated fields and backend results in an Advanced child window.";
            open.Click += delegate
            {
                MainForm explorer = new MainForm();
                explorer.Text = "FacMan Advanced Command Explorer";
                explorer.Show(this);
            };
            actions.Controls.Add(open);
            layout.Controls.Add(actions, 0, 2);
            return page;
        }

        private Control BuildLaunchDeck()
        {
            GroupBox deck = new GroupBox();
            deck.Text = "Launch Deck";
            deck.Dock = DockStyle.Top;
            deck.AutoSize = true;
            deck.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            deck.Padding = new Padding(10);
            deck.AccessibleName = "Persistent Launch Deck";
            deck.AccessibleDescription = "Selected instance readiness, primary action, Last Run, refusal, and recovery truth.";

            TableLayoutPanel layout = new TableLayoutPanel();
            layout.Dock = DockStyle.Top;
            layout.AutoSize = true;
            layout.ColumnCount = 4;
            layout.RowCount = 3;
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 28F));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 28F));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 24F));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20F));
            deck.Controls.Add(layout);

            deckInstance = DeckLabel("Selected instance");
            deckStatus = DeckLabel("Launch status");
            deckReadiness = DeckLabel("Readiness status");
            deckLastRun = DeckLabel("Last Run");
            layout.Controls.Add(deckInstance, 0, 0);
            layout.Controls.Add(deckStatus, 1, 0);
            layout.Controls.Add(deckReadiness, 2, 0);
            layout.Controls.Add(deckLastRun, 3, 0);

            deckRefusal = DeckLabel("Launch Deck refusal and recovery detail");
            deckRefusal.ForeColor = SystemColors.ControlText;
            layout.SetColumnSpan(deckRefusal, 3);
            layout.Controls.Add(deckRefusal, 0, 1);

            FlowLayoutPanel actions = ActionRow();
            primaryAction = ActionButton("&Play", "Launch Deck primary action", "instance.play");
            primaryAction.Font = new Font(SystemFonts.MessageBoxFont, FontStyle.Bold);
            primaryAction.MinimumSize = new Size(150, 38);
            secondaryAction = ActionButton("&Rescan readiness", "Launch Deck secondary action", "instance.readiness.refresh");
            actions.Controls.Add(primaryAction);
            actions.Controls.Add(secondaryAction);
            layout.Controls.Add(actions, 3, 1);

            Label notice = DeckLabel("Fixture authority notice");
            notice.Text = "Deterministic fixture presentation — no live Play authority.";
            notice.ForeColor = SystemColors.GrayText;
            layout.SetColumnSpan(notice, 4);
            layout.Controls.Add(notice, 0, 2);
            return deck;
        }

        private void RenderPresentation()
        {
            rendering = true;
            try
            {
                C1Presentation view = presentationStore.Current;
                string name = view.Text("selected_instance", "name");
                string journey = view.Text("selected_instance", "journey_state");
                string readiness = view.Text("selected_instance", "readiness", "state");
                string readinessText = view.Text("selected_instance", "readiness", "summary");
                string installation = view.Text("selected_instance", "installation", "label");

                instancesSummary.Text = view.Text("pages", "instances", "summary");
                instancesList.Items.Clear();
                ListViewItem instance = new ListViewItem(name);
                instance.SubItems.Add(readiness);
                instance.SubItems.Add(journey);
                instance.SubItems.Add(installation);
                instance.Selected = true;
                instancesList.Items.Add(instance);
                readinessSummary.Text = "Readiness: " + readiness + " (revision " +
                    view.Number("selected_instance", "readiness", "revision") + ")\r\n" + readinessText;

                string refusalCode = view.Text("refusal", "code");
                refusalDetail.Visible = !String.IsNullOrWhiteSpace(refusalCode);
                refusalDetail.Text = RefusalText(view);

                installationsSummary.Text = view.Text("pages", "installations", "summary");
                installationsList.Items.Clear();
                ListViewItem install = new ListViewItem(installation);
                install.SubItems.Add(view.Text("selected_instance", "installation", "kind"));
                install.SubItems.Add(view.Text("selected_instance", "installation", "version"));
                installationsList.Items.Add(install);

                activitySummary.Text = view.Text("pages", "activity", "summary");
                RenderOperations(view);
                RenderRecoveryActions(view);

                deckInstance.Text = "Instance\r\n" + name;
                deckStatus.Text = "Status\r\n" + view.Text("launch_deck", "status_text");
                deckReadiness.Text = "Readiness\r\n" + readiness + " · revision " +
                    view.Number("selected_instance", "readiness", "revision");
                deckLastRun.Text = "Last Run\r\n" + LastRunText(view);
                deckRefusal.Text = String.IsNullOrWhiteSpace(refusalCode)
                    ? RecoveryText(view) : RefusalText(view);

                IDictionary<string, object> primary = view.Record("launch_deck", "primary_action");
                ConfigureAction(primaryAction, primary, true);
                IList<object> secondaries = view.Records("launch_deck", "secondary_actions");
                ConfigureAction(secondaryAction,
                    secondaries.Count == 0 ? null : secondaries[0] as IDictionary<string, object>, false);
                AcceptButton = primaryAction;

                evidenceScope.Text = "Presentation: " + view.Contract + "\r\n" +
                    "Fixture state: " + view.FixtureState + "\r\nAuthority scope: " + view.AuthorityScope;
                evidenceState.SelectedItem = view.FixtureState;
                Announce("Showing " + view.FixtureState + " fixture state.");
            }
            finally
            {
                rendering = false;
            }
        }

        private void RenderOperations(C1Presentation view)
        {
            activityList.Items.Clear();
            foreach (object value in view.Records("pages", "activity", "operations"))
            {
                IDictionary<string, object> operation = value as IDictionary<string, object>;
                if (operation == null) continue;
                ListViewItem item = new ListViewItem(RecordText(operation, "operation_id"));
                item.SubItems.Add(RecordText(operation, "status"));
                IDictionary<string, object> progress = Record(operation, "progress");
                item.SubItems.Add(RecordText(progress, "completed") + "/" + RecordText(progress, "total") +
                    " " + RecordText(progress, "unit"));
                item.SubItems.Add(RecordText(operation, "summary"));
                activityList.Items.Add(item);
            }
        }

        private void RenderRecoveryActions(C1Presentation view)
        {
            activityActions.Controls.Clear();
            foreach (object value in view.Records("pages", "activity", "actions"))
            {
                IDictionary<string, object> action = value as IDictionary<string, object>;
                if (action == null) continue;
                activityActions.Controls.Add(ActionButton(
                    "&" + RecordText(action, "label"),
                    RecordText(action, "accessibility_label"),
                    RecordText(action, "action_id")));
            }
            if (activityActions.Controls.Count == 0)
            {
                Label none = BodyLabel("No recovery action required");
                none.Text = "No recovery action is required.";
                activityActions.Controls.Add(none);
            }
        }

        private void ConfigureAction(Button button, IDictionary<string, object> action, bool primary)
        {
            if (action == null)
            {
                button.Visible = false;
                return;
            }
            string label = RecordText(action, "label");
            string availability = RecordText(action, "availability");
            button.Visible = true;
            button.Text = "&" + label + (availability == "refused" ? " (refused)" : String.Empty);
            button.Tag = RecordText(action, "action_id");
            button.AccessibleName = RecordText(action, "accessibility_label");
            button.AccessibleDescription = primary
                ? "Launch Deck primary action. Backend-owned semantics; fixture-only execution in this prototype."
                : "Launch Deck secondary action. Backend-owned semantics.";
            button.Enabled = availability == "available" || availability == "refused";
            toolTip.SetToolTip(button, RecordText(action, "command_id") + " | " + availability);
        }

        private void InvokeAction(string actionId)
        {
            C1Presentation view = presentationStore.Current;
            if (actionId == "instance.play" && view.FixtureState == "refused")
            {
                string message = RefusalText(view);
                Announce("Play refused: stale_readiness. No process was started.");
                MessageBox.Show(this, message, "Play refused", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            if (actionId == "instance.create")
            {
                DialogResult answer = MessageBox.Show(this,
                    "Select the deterministic C1 Vanilla fixture instance? No live files will be changed.",
                    "Create fixture instance", MessageBoxButtons.OKCancel, MessageBoxIcon.Information);
                if (answer != DialogResult.OK) return;
                presentationStore.Select("positive");
            }
            else if (actionId == "activity.show_operation" || actionId == "recovery.inspect")
            {
                pages.SelectedIndex = 2;
                activityList.Focus();
                Announce("Showing the exact backend operation and recovery identity in Activity.");
                return;
            }
            else if (actionId == "recovery.apply")
            {
                DialogResult answer = MessageBox.Show(this,
                    "Recover the deterministic fixture record? Recovery does not auto-launch.",
                    "Recover operation", MessageBoxButtons.OKCancel, MessageBoxIcon.Warning);
                if (answer != DialogResult.OK) return;
                presentationStore.Apply(actionId);
            }
            else
            {
                presentationStore.Apply(actionId);
            }
            RenderPresentation();
        }

        private void SelectEvidenceState(string state)
        {
            presentationStore.Select(state);
            RenderPresentation();
        }

        private void Announce(string message)
        {
            statusLabel.Text = message;
            statusLabel.AccessibleName = "FacMan status: " + message;
            AccessibilityNotifyClients(AccessibleEvents.NameChange, -1);
        }

        private static string LastRunText(C1Presentation view)
        {
            if (!view.Has("launch_deck", "last_run")) return "No recorded run";
            string outcome = view.Text("launch_deck", "last_run", "outcome");
            string operation = view.Text("launch_deck", "last_run", "operation_id");
            string exit = view.Text("launch_deck", "last_run", "exit_code");
            return outcome + (String.IsNullOrWhiteSpace(exit) ? String.Empty : " · exit " + exit) + "\r\n" + operation;
        }

        private static string RefusalText(C1Presentation view)
        {
            string code = view.Text("refusal", "code");
            if (String.IsNullOrWhiteSpace(code)) return String.Empty;
            return code + " · observed revision " + view.Number("refusal", "observed_readiness_revision") +
                ", current revision " + view.Number("refusal", "current_readiness_revision") +
                "\r\n" + view.Text("refusal", "detail") + " Action: Rescan readiness.";
        }

        private static string RecoveryText(C1Presentation view)
        {
            if (view.Text("recovery", "state") != "required") return "No structured refusal or recovery action is active.";
            return view.Text("recovery", "reason_code") + " · " + view.Text("recovery", "recovery_id") +
                " · " + view.Text("recovery", "operation_id") + "\r\n" + view.Text("recovery", "summary");
        }

        private Button ActionButton(string text, string accessibleName, string actionId)
        {
            Button button = new Button();
            button.Text = text;
            button.AutoSize = true;
            button.MinimumSize = new Size(140, 36);
            button.Margin = new Padding(0, 0, 8, 0);
            button.Tag = actionId;
            button.AccessibleName = accessibleName;
            button.AccessibleDescription = "FacMan presentation action " + actionId + ".";
            button.Click += delegate { InvokeAction(Convert.ToString(button.Tag)); };
            return button;
        }

        private static TabPage Page(string title, string accessibleName)
        {
            TabPage page = new TabPage(title);
            page.Padding = new Padding(12);
            page.AccessibleName = accessibleName;
            return page;
        }

        private static TableLayoutPanel PageLayout(int rows)
        {
            TableLayoutPanel layout = new TableLayoutPanel();
            layout.Dock = DockStyle.Fill;
            layout.ColumnCount = 1;
            layout.RowCount = rows;
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            for (int i = 0; i < rows; ++i)
                layout.RowStyles.Add(new RowStyle(i == 2 ? SizeType.Percent : SizeType.AutoSize, i == 2 ? 100F : 0F));
            return layout;
        }

        private static Control Heading(string title, string explanation)
        {
            TableLayoutPanel heading = new TableLayoutPanel();
            heading.Dock = DockStyle.Top;
            heading.AutoSize = true;
            heading.RowCount = 2;
            Label titleLabel = new Label();
            titleLabel.Text = title;
            titleLabel.Font = new Font(SystemFonts.MessageBoxFont.FontFamily, 15F, FontStyle.Bold);
            titleLabel.AutoSize = true;
            titleLabel.AccessibleName = title + " heading";
            Label explanationLabel = new Label();
            explanationLabel.Text = explanation;
            explanationLabel.AutoSize = true;
            explanationLabel.ForeColor = SystemColors.GrayText;
            explanationLabel.AccessibleName = title + " explanation";
            heading.Controls.Add(titleLabel, 0, 0);
            heading.Controls.Add(explanationLabel, 0, 1);
            return heading;
        }

        private static Label BodyLabel(string accessibleName)
        {
            Label label = new Label();
            label.AutoSize = true;
            label.MaximumSize = new Size(900, 0);
            label.Margin = new Padding(0, 8, 0, 8);
            label.AccessibleName = accessibleName;
            return label;
        }

        private static Label DeckLabel(string accessibleName)
        {
            Label label = BodyLabel(accessibleName);
            label.Dock = DockStyle.Fill;
            label.AutoSize = true;
            label.Margin = new Padding(6);
            return label;
        }

        private static FlowLayoutPanel ActionRow()
        {
            FlowLayoutPanel row = new FlowLayoutPanel();
            row.Dock = DockStyle.Fill;
            row.AutoSize = true;
            row.WrapContents = true;
            row.FlowDirection = FlowDirection.LeftToRight;
            row.Padding = new Padding(0, 8, 0, 4);
            return row;
        }

        private static IDictionary<string, object> Record(IDictionary<string, object> parent, string key)
        {
            object value;
            return parent != null && parent.TryGetValue(key, out value)
                ? value as IDictionary<string, object> : null;
        }

        private static string RecordText(IDictionary<string, object> record, string key)
        {
            object value;
            return record != null && record.TryGetValue(key, out value) && value != null
                ? Convert.ToString(value) : String.Empty;
        }
    }
}
