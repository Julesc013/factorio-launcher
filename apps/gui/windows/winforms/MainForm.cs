// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

using System;
using System.Collections.Generic;
using System.Drawing;
using System.Threading;
using System.Windows.Forms;

namespace FacMan.WinForms
{
    public sealed class MainForm : Form
    {
        private readonly CommandClient commandClient;
        private readonly IList<CommandDefinition> commandCatalog;
        private readonly ToolTip toolTip;
        private CancellationTokenSource commandCancellation;
        private TextBox resultBox;
        private TextBox cliPathBox;
        private TextBox workspaceBox;
        private ToolStripStatusLabel statusLabel;

        public MainForm()
        {
            commandClient = new CommandClient();
            commandCatalog = CommandCatalog.All();
            toolTip = new ToolTip();

            Text = "FacMan WinForms Shell";
            Width = 1120;
            Height = 760;
            MinimumSize = new Size(900, 620);
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;
            AccessibleName = "FacMan operations window";
            AccessibleDescription = "Guided command forms generated from the FacMan command grammar.";

            BuildLayout();
            LoadDefaults();
            RenderMessage("Ready. Configure a facman executable if it is not colocated with this GUI.");
            FormClosed += delegate
            {
                if (commandCancellation != null) commandCancellation.Cancel();
            };
        }

        private void BuildLayout()
        {
            TableLayoutPanel root = new TableLayoutPanel();
            root.Dock = DockStyle.Fill;
            root.ColumnCount = 1;
            root.RowCount = 4;
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 64));
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 220));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));
            Controls.Add(root);

            root.Controls.Add(BuildCommandBar(), 0, 0);

            TabControl tabs = new TabControl();
            tabs.Dock = DockStyle.Fill;
            root.Controls.Add(tabs, 0, 1);

            AddDashboardTab(tabs);
            AddDoctorTab(tabs);
            AddInstallsTab(tabs);
            AddGeneratedCategoryTab(tabs, "Instances", "instance.");
            AddGeneratedCategoryTab(tabs, "Snapshots", "snapshots.");
            AddGeneratedCategoryTab(tabs, "Profiles", "profiles.", "templates.");
            AddGeneratedCategoryTab(tabs, "Launch Plan", "launch_plan.", "run.");
            AddGeneratedCategoryTab(tabs, "Mods", "mods.", "modsets.");
            AddGeneratedCategoryTab(tabs, "Saves", "saves.");
            AddGeneratedCategoryTab(tabs, "Servers", "servers.");
            AddGeneratedCategoryTab(tabs, "Diagnostics", "diagnostics.", "dev.");
            AddGeneratedCategoryTab(tabs, "Recovery", "workspace.recovery.", "workspace.migration.");
            AddGeneratedCategoryTab(tabs, "Capabilities", "capabilities.", "workspace.");
            AddSettingsTab(tabs);

            resultBox = new TextBox();
            resultBox.Dock = DockStyle.Fill;
            resultBox.Multiline = true;
            resultBox.ScrollBars = ScrollBars.Both;
            resultBox.ReadOnly = true;
            resultBox.WordWrap = false;
            resultBox.Font = new Font(FontFamily.GenericMonospace, 9.0f);
            resultBox.AccessibleName = "Command result";
            resultBox.AccessibleDescription = "Structured command result, refusal, or operational visualization.";
            root.Controls.Add(resultBox, 0, 2);

            StatusStrip statusStrip = new StatusStrip();
            statusLabel = new ToolStripStatusLabel("Ready");
            statusLabel.AccessibleName = "Command status";
            statusStrip.Items.Add(statusLabel);
            root.Controls.Add(statusStrip, 0, 3);
        }

        private Control BuildCommandBar()
        {
            TableLayoutPanel bar = new TableLayoutPanel();
            bar.Dock = DockStyle.Fill;
            bar.Padding = new Padding(8);
            bar.ColumnCount = 6;
            bar.RowCount = 2;
            bar.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 72));
            bar.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
            bar.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 86));
            bar.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
            bar.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 88));
            bar.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 88));
            bar.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
            bar.RowStyles.Add(new RowStyle(SizeType.Percent, 50));

            Label cliLabel = new Label();
            cliLabel.Text = "CLI path";
            cliLabel.TextAlign = ContentAlignment.MiddleLeft;
            bar.Controls.Add(cliLabel, 0, 0);

            cliPathBox = new TextBox();
            cliPathBox.Dock = DockStyle.Fill;
            cliPathBox.AccessibleName = "FacMan CLI path";
            bar.Controls.Add(cliPathBox, 1, 0);

            Button browseButton = new Button();
            browseButton.Text = "Browse";
            browseButton.Dock = DockStyle.Fill;
            browseButton.Click += delegate { BrowseCliPath(); };
            bar.Controls.Add(browseButton, 4, 0);

            Button helpButton = new Button();
            helpButton.Text = "Status";
            helpButton.Dock = DockStyle.Fill;
            helpButton.Click += delegate { RunGeneratedCommand("workspace.status"); };
            bar.Controls.Add(helpButton, 5, 0);

            Label workspaceLabel = new Label();
            workspaceLabel.Text = "Workspace";
            workspaceLabel.TextAlign = ContentAlignment.MiddleLeft;
            bar.Controls.Add(workspaceLabel, 0, 1);

            workspaceBox = new TextBox();
            workspaceBox.Dock = DockStyle.Fill;
            workspaceBox.AccessibleName = "Workspace path";
            bar.Controls.Add(workspaceBox, 1, 1);

            Label modeLabel = new Label();
            modeLabel.Text = "CLI JSON";
            modeLabel.TextAlign = ContentAlignment.MiddleLeft;
            bar.Controls.Add(modeLabel, 2, 1);

            Button cancelButton = new Button();
            cancelButton.Text = "Cancel";
            cancelButton.AccessibleDescription = "Request cancellation of the active backend command.";
            cancelButton.Dock = DockStyle.Fill;
            cancelButton.Click += delegate { if (commandCancellation != null) commandCancellation.Cancel(); };
            bar.Controls.Add(cancelButton, 3, 1);

            Button versionButton = new Button();
            versionButton.Text = "Product";
            versionButton.Dock = DockStyle.Fill;
            versionButton.Click += delegate { RunGeneratedCommand("product.inspect"); };
            bar.Controls.Add(versionButton, 4, 1);

            Button doctorButton = new Button();
            doctorButton.Text = "Doctor";
            doctorButton.Dock = DockStyle.Fill;
            doctorButton.Click += delegate { RunGeneratedCommand("doctor.run"); };
            bar.Controls.Add(doctorButton, 5, 1);

            return bar;
        }

        private void AddDashboardTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Dashboard");
            TableLayoutPanel layout = CreateTabLayout();
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));
            page.Controls.Add(layout);

            Label title = SectionTitle("Shared command graph surface");
            layout.Controls.Add(title, 0, 0);

            ListView list = new ListView();
            list.Dock = DockStyle.Fill;
            list.View = View.Details;
            list.FullRowSelect = true;
            list.Columns.Add("Command", 170);
            list.Columns.Add("Backend", 170);
            list.Columns.Add("Screen", 120);
            list.Columns.Add("Status", 160);
            list.Columns.Add("Reason", 420);
            foreach (CommandDefinition command in commandCatalog)
            {
                ListViewItem item = new ListViewItem(command.Id);
                item.SubItems.Add(command.BackendId);
                item.SubItems.Add(command.Screen);
                item.SubItems.Add(StatusText(command.Status));
                item.SubItems.Add(command.DeferredReason);
                list.Items.Add(item);
            }
            layout.Controls.Add(list, 0, 1);

            FlowLayoutPanel actions = new FlowLayoutPanel();
            actions.Dock = DockStyle.Fill;
            actions.FlowDirection = FlowDirection.LeftToRight;
            actions.Controls.Add(CommandButton("Product Inspect", "product.inspect"));
            actions.Controls.Add(CommandButton("Capabilities", "capabilities.inspect"));
            actions.Controls.Add(CommandButton("Workspace Status", "workspace.status"));
            layout.Controls.Add(actions, 0, 2);
        }

        private void AddDoctorTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Doctor");
            FlowLayoutPanel panel = CreateFlowPanel();
            page.Controls.Add(panel);
            panel.Controls.Add(SectionTitle("Workspace checks"));
            panel.Controls.Add(CommandButton("Run Doctor", "doctor.run"));
            panel.Controls.Add(CommandButton("Inspect Product", "product.inspect"));
            panel.Controls.Add(CommandButton("Explain Doctor", "doctor.explain"));
        }

        private void AddGeneratedCategoryTab(TabControl tabs, string title, params string[] prefixes)
        {
            TabPage page = CreateTab(tabs, title);
            TableLayoutPanel form = CreateFormPanel();
            page.Controls.Add(form);
            AddGeneratedCommands(form, prefixes);
        }

        private void AddInstallsTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Installs");
            TableLayoutPanel layout = new TableLayoutPanel();
            layout.Dock = DockStyle.Fill;
            layout.RowCount = 2;
            layout.ColumnCount = 1;
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 280));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            page.Controls.Add(layout);

            TextBox workflow = new TextBox();
            workflow.Multiline = true;
            workflow.ReadOnly = true;
            workflow.ScrollBars = ScrollBars.Vertical;
            workflow.Dock = DockStyle.Fill;
            workflow.AccessibleName = "Managed portable setup workflow";
            workflow.Text = GeneratedCommandCatalog.SetupWorkflowText.Replace("\n", "\r\n");
            layout.Controls.Add(workflow, 0, 0);

            TableLayoutPanel form = CreateFormPanel();
            layout.Controls.Add(form, 0, 1);
            AddGeneratedCommands(form, "install_refs.", "installs.", "setup.");
        }

        private void AddGeneratedCommands(TableLayoutPanel form, params string[] prefixes)
        {
            foreach (CommandDefinition command in commandCatalog)
            {
                bool included = false;
                foreach (string prefix in prefixes)
                    if (command.BackendId.StartsWith(prefix, StringComparison.Ordinal)) included = true;
                if (!included) continue;
                int row = form.RowCount++;
                form.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));
                Label label = new Label();
                label.Text = command.Label + "\r\n" + command.BackendId;
                label.Dock = DockStyle.Fill;
                label.TextAlign = ContentAlignment.MiddleLeft;
                form.Controls.Add(label, 0, row);
                Label detail = new Label();
                detail.Text = command.Availability + " | " + command.RiskTier +
                    (String.IsNullOrWhiteSpace(command.DeferredReason) ? String.Empty : " | " + command.DeferredReason);
                detail.Dock = DockStyle.Fill;
                detail.TextAlign = ContentAlignment.MiddleLeft;
                form.Controls.Add(detail, 1, row);
                Button button = CommandButton(command.Status == CommandStatus.Implemented ? "Open" : "Explain", command.Id);
                button.Dock = DockStyle.Fill;
                form.Controls.Add(button, 2, row);
            }
        }

        private void AddSettingsTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Settings/About");
            FlowLayoutPanel panel = CreateFlowPanel();
            page.Controls.Add(panel);

            Label about = SectionTitle("FacMan WinForms shell");
            panel.Controls.Add(about);

            TextBox info = new TextBox();
            info.Multiline = true;
            info.ReadOnly = true;
            info.Width = 960;
            info.Height = 260;
            info.ScrollBars = ScrollBars.Vertical;
            info.Text =
                "FACMAN-WINFORMS-SHELL-01\r\n\r\n" +
                "This app is a thin Windows Forms frontend over the shared FacMan command graph.\r\n" +
                "It renders required command results returned by the configured backend path and keeps deferred commands disabled or refused with reasons.\r\n\r\n" +
                "It does not implement Factorio discovery logic, setup mutation, Mod Portal network access, modset resolution, " +
                "save/export/import behavior, server execution, developer execution, credential storage, " +
                "or direct Factorio launch behavior in C#.\r\n\r\n" +
                "Set FACMAN_CLI or use the CLI path field above to point at a built facman executable.";
            panel.Controls.Add(info);

            panel.Controls.Add(CommandButton("Workspace Paths", "workspace.paths"));
            panel.Controls.Add(CommandButton("Capabilities", "capabilities.inspect"));
        }

        private Button CommandButton(string text, string commandId)
        {
            CommandDefinition command = CommandCatalog.Find(commandId);
            Button button = new Button();
            button.Text = text;
            button.Width = 150;
            button.Height = 32;
            button.Tag = commandId;
            toolTip.SetToolTip(button, command.Id + " -> " + command.BackendId + " | " + command.RiskTier);
            button.Click += delegate { RunGeneratedCommand(commandId); };
            return button;
        }

        private void RunGeneratedCommand(string commandId)
        {
            CommandDefinition command = CommandCatalog.Find(commandId);
            Dictionary<string, string> inputs;
            if (!CollectGeneratedInputs(command, out inputs)) return;
            RunCommand(commandId, inputs);
        }

        private bool CollectGeneratedInputs(CommandDefinition command, out Dictionary<string, string> inputs)
        {
            inputs = new Dictionary<string, string>();
            if (command.Status != CommandStatus.Implemented || command.Inputs.Count == 0) return true;
            Form dialog = new Form();
            dialog.Text = command.Label + " | " + command.RiskTier;
            dialog.Width = 660;
            dialog.Height = Math.Min(700, 160 + command.Inputs.Count * 64);
            dialog.StartPosition = FormStartPosition.CenterParent;
            TableLayoutPanel layout = new TableLayoutPanel();
            layout.Dock = DockStyle.Fill;
            layout.Padding = new Padding(12);
            layout.ColumnCount = 3;
            layout.RowCount = command.Inputs.Count + 2;
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 80));
            dialog.Controls.Add(layout);
            Dictionary<string, Control> controls = new Dictionary<string, Control>();
            int row = 0;
            foreach (CommandInput input in command.Inputs)
            {
                Label label = new Label();
                label.Text = input.Label + (input.Required ? " *" : String.Empty);
                label.AccessibleName = input.Label;
                label.Dock = DockStyle.Fill;
                label.TextAlign = ContentAlignment.MiddleLeft;
                layout.Controls.Add(label, 0, row);
                Control editor;
                if (input.Type == "boolean") editor = new CheckBox();
                else if (input.Choices.Count > 0)
                {
                    ComboBox choice = new ComboBox();
                    choice.DropDownStyle = ComboBoxStyle.DropDownList;
                    foreach (string value in input.Choices) choice.Items.Add(value);
                    if (!input.Required) choice.Items.Insert(0, String.Empty);
                    choice.SelectedIndex = 0;
                    editor = choice;
                }
                else
                {
                    TextBox text = new TextBox();
                    text.Dock = DockStyle.Fill;
                    text.Text = input.DefaultValue ?? String.Empty;
                    text.Multiline = input.Repeatable;
                    editor = text;
                }
                editor.Dock = DockStyle.Fill;
                editor.AccessibleName = input.Label;
                editor.AccessibleDescription = (input.Required ? "Required " : "Optional ") + input.Type + " field.";
                controls[input.Key] = editor;
                layout.Controls.Add(editor, 1, row);
                if (input.Type == "path")
                {
                    Button browse = new Button();
                    browse.Text = "Browse";
                    browse.Click += delegate
                    {
                        SaveFileDialog chooser = new SaveFileDialog();
                        chooser.CheckFileExists = false;
                        if (chooser.ShowDialog(dialog) == DialogResult.OK) ((TextBox)editor).Text = chooser.FileName;
                    };
                    layout.Controls.Add(browse, 2, row);
                }
                row++;
            }
            Label policy = new Label();
            policy.Text = "Availability: " + command.Availability + " | Effects: " + String.Join(", ", command.Effects);
            policy.Dock = DockStyle.Fill;
            layout.SetColumnSpan(policy, 2);
            layout.Controls.Add(policy, 0, row);
            FlowLayoutPanel actions = new FlowLayoutPanel();
            actions.FlowDirection = FlowDirection.RightToLeft;
            Button ok = new Button();
            ok.Text = command.DryRunDefault ? "Run" : "Apply";
            ok.DialogResult = DialogResult.OK;
            Button cancel = new Button(); cancel.Text = "Cancel"; cancel.DialogResult = DialogResult.Cancel;
            actions.Controls.Add(ok); actions.Controls.Add(cancel);
            layout.Controls.Add(actions, 1, row + 1);
            dialog.AcceptButton = ok;
            dialog.CancelButton = cancel;
            if (dialog.ShowDialog(this) != DialogResult.OK) return false;
            foreach (CommandInput input in command.Inputs)
            {
                CheckBox check = controls[input.Key] as CheckBox;
                inputs[input.Key] = check == null ? controls[input.Key].Text : (check.Checked ? "true" : "false");
            }
            return true;
        }

        private async void RunCommand(string commandId, Dictionary<string, string> inputs)
        {
            CommandDefinition command = CommandCatalog.Find(commandId);
            if (commandCancellation != null) commandCancellation.Cancel();
            commandCancellation = new CancellationTokenSource();
            statusLabel.Text = "Running " + command.Id;
            UseWaitCursor = true;
            try
            {
                CommandResult result = await commandClient.ExecuteAsync(
                    command,
                    inputs,
                    workspaceBox.Text,
                    cliPathBox.Text,
                    commandCancellation.Token);
                RenderMessage(OperationalVisualization.Render(command, result));
                statusLabel.Text = result.Success ? "Completed " + command.Id : "Completed with refusal or error: " + command.Id;
            }
            finally
            {
                UseWaitCursor = false;
            }
        }

        private void BrowseCliPath()
        {
            OpenFileDialog dialog = new OpenFileDialog();
            dialog.Title = "Select facman executable";
            dialog.Filter = "Executables|*.exe|All files|*.*";
            if (dialog.ShowDialog(this) == DialogResult.OK)
            {
                cliPathBox.Text = dialog.FileName;
            }
        }

        private void LoadDefaults()
        {
            string envCli = Environment.GetEnvironmentVariable("FACMAN_CLI");
            if (!String.IsNullOrWhiteSpace(envCli))
            {
                cliPathBox.Text = envCli;
            }

            workspaceBox.Text = String.Empty;
        }

        private void RenderMessage(string text)
        {
            resultBox.Text = text;
            resultBox.SelectionStart = resultBox.TextLength;
            resultBox.ScrollToCaret();
        }

        private static TabPage CreateTab(TabControl tabs, string title)
        {
            TabPage page = new TabPage(title);
            page.Padding = new Padding(8);
            tabs.TabPages.Add(page);
            return page;
        }

        private static TableLayoutPanel CreateTabLayout()
        {
            TableLayoutPanel layout = new TableLayoutPanel();
            layout.Dock = DockStyle.Fill;
            layout.ColumnCount = 1;
            layout.RowCount = 0;
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            return layout;
        }

        private static FlowLayoutPanel CreateFlowPanel()
        {
            FlowLayoutPanel panel = new FlowLayoutPanel();
            panel.Dock = DockStyle.Fill;
            panel.FlowDirection = FlowDirection.TopDown;
            panel.WrapContents = false;
            panel.AutoScroll = true;
            panel.Padding = new Padding(8);
            return panel;
        }

        private static TableLayoutPanel CreateFormPanel()
        {
            TableLayoutPanel form = new TableLayoutPanel();
            form.Dock = DockStyle.Fill;
            form.Padding = new Padding(8);
            form.AutoScroll = true;
            form.ColumnCount = 3;
            form.RowCount = 0;
            form.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 160));
            form.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            form.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));
            return form;
        }

        private static Label SectionTitle(string text)
        {
            Label label = new Label();
            label.Text = text;
            label.Font = new Font(SystemFonts.DefaultFont, FontStyle.Bold);
            label.AutoSize = false;
            label.Width = 960;
            label.Height = 34;
            label.TextAlign = ContentAlignment.MiddleLeft;
            return label;
        }

        private static string StatusText(CommandStatus status)
        {
            if (status == CommandStatus.Implemented)
            {
                return "implemented";
            }
            if (status == CommandStatus.StubbedWithRefusal)
            {
                return "stubbed_with_refusal";
            }
            return "not_supported_with_reason";
        }
    }
}
