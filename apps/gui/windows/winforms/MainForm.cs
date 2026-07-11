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
            AddInstancesTab(tabs);
            AddLaunchPlanTab(tabs);
            AddDiagnosticsTab(tabs);
            AddSettingsTab(tabs);

            resultBox = new TextBox();
            resultBox.Dock = DockStyle.Fill;
            resultBox.Multiline = true;
            resultBox.ScrollBars = ScrollBars.Both;
            resultBox.ReadOnly = true;
            resultBox.WordWrap = false;
            resultBox.Font = new Font(FontFamily.GenericMonospace, 9.0f);
            root.Controls.Add(resultBox, 0, 2);

            StatusStrip statusStrip = new StatusStrip();
            statusLabel = new ToolStripStatusLabel("Ready");
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
            bar.Controls.Add(cliPathBox, 1, 0);

            Button browseButton = new Button();
            browseButton.Text = "Browse";
            browseButton.Dock = DockStyle.Fill;
            browseButton.Click += delegate { BrowseCliPath(); };
            bar.Controls.Add(browseButton, 4, 0);

            Button helpButton = new Button();
            helpButton.Text = "Help";
            helpButton.Dock = DockStyle.Fill;
            helpButton.Click += delegate { RunCommand("help", EmptyInputs()); };
            bar.Controls.Add(helpButton, 5, 0);

            Label workspaceLabel = new Label();
            workspaceLabel.Text = "Workspace";
            workspaceLabel.TextAlign = ContentAlignment.MiddleLeft;
            bar.Controls.Add(workspaceLabel, 0, 1);

            workspaceBox = new TextBox();
            workspaceBox.Dock = DockStyle.Fill;
            bar.Controls.Add(workspaceBox, 1, 1);

            Label modeLabel = new Label();
            modeLabel.Text = "Transport";
            modeLabel.TextAlign = ContentAlignment.MiddleLeft;
            bar.Controls.Add(modeLabel, 2, 1);

            Label modeValue = new Label();
            modeValue.Text = "CLI JSON";
            modeValue.TextAlign = ContentAlignment.MiddleLeft;
            bar.Controls.Add(modeValue, 3, 1);

            Button versionButton = new Button();
            versionButton.Text = "Version";
            versionButton.Dock = DockStyle.Fill;
            versionButton.Click += delegate { RunCommand("version", EmptyInputs()); };
            bar.Controls.Add(versionButton, 4, 1);

            Button doctorButton = new Button();
            doctorButton.Text = "Doctor";
            doctorButton.Dock = DockStyle.Fill;
            doctorButton.Click += delegate { RunCommand("doctor", EmptyInputs()); };
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
            actions.Controls.Add(CommandButton("Product Inspect", "product.inspect", EmptyInputs));
            actions.Controls.Add(CommandButton("Command Graph", "command_graph.inspect", EmptyInputs));
            actions.Controls.Add(CommandButton("Diagnostics", "diagnostics.export", EmptyInputs));
            layout.Controls.Add(actions, 0, 2);
        }

        private void AddDoctorTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Doctor");
            FlowLayoutPanel panel = CreateFlowPanel();
            page.Controls.Add(panel);
            panel.Controls.Add(SectionTitle("Workspace checks"));
            panel.Controls.Add(CommandButton("Run Doctor", "doctor", EmptyInputs));
            panel.Controls.Add(CommandButton("Inspect Product", "product.inspect", EmptyInputs));
            panel.Controls.Add(CommandButton("Inspect Command Graph", "command_graph.inspect", EmptyInputs));
        }

        private void AddInstallsTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Installs");
            TableLayoutPanel form = CreateFormPanel();
            page.Controls.Add(form);

            TextBox scanPath = AddTextInput(form, "Scan root", "Optional folder to scan");
            AddCommandRow(form, "installs.scan", "Scan", delegate
            {
                return Inputs("scanPath", scanPath.Text);
            });

            TextBox installPath = AddTextInput(form, "Install path", "Existing Factorio folder");
            TextBox installId = AddTextInput(form, "Install id", "fixture");
            AddCommandRow(form, "installs.import", "Import", delegate
            {
                return Inputs("installPath", installPath.Text, "installId", installId.Text);
            });

            TextBox inspectId = AddTextInput(form, "Inspect id", "fixture");
            AddCommandRow(form, "installs.inspect", "Inspect", delegate
            {
                return Inputs("installId", inspectId.Text);
            });

            AddDeferredRow(form, "setup.preview");
        }

        private void AddInstancesTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Instances");
            TableLayoutPanel form = CreateFormPanel();
            page.Controls.Add(form);

            AddCommandRow(form, "instances.list", "List", EmptyInputs);

            TextBox instanceName = AddTextInput(form, "Instance name", "Space Age Main");
            TextBox installId = AddTextInput(form, "Install id", "fixture");
            TextBox templateId = AddTextInput(form, "Template id", "vanilla");
            AddCommandRow(form, "instances.create", "Create", delegate
            {
                return Inputs("instanceName", instanceName.Text, "installId", installId.Text, "templateId", templateId.Text);
            });
        }

        private void AddLaunchPlanTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Launch Plan");
            TableLayoutPanel form = CreateFormPanel();
            page.Controls.Add(form);

            TextBox instanceId = AddTextInput(form, "Instance id", "space-age-main");
            AddCommandRow(form, "launch_plan.build", "Build Plan", delegate
            {
                return Inputs("instanceId", instanceId.Text);
            });
            AddCommandRow(form, "launch_plan.preflight", "Preflight", delegate
            {
                return Inputs("instanceId", instanceId.Text);
            });
            AddCommandRow(form, "run.preview", "Preview Run", delegate
            {
                return Inputs("instanceId", instanceId.Text);
            });
            AddDeferredRow(form, "run.execute");
        }

        private void AddDiagnosticsTab(TabControl tabs)
        {
            TabPage page = CreateTab(tabs, "Diagnostics");
            TableLayoutPanel form = CreateFormPanel();
            page.Controls.Add(form);

            AddCommandRow(form, "diagnostics.export", "Export Diagnostics", EmptyInputs);
            AddDeferredRow(form, "modsets.lock");
            AddDeferredRow(form, "saves.backup");
            AddDeferredRow(form, "instance.export");
            AddDeferredRow(form, "instance.import");
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

            panel.Controls.Add(CommandButton("Run Help", "help", EmptyInputs));
            panel.Controls.Add(CommandButton("Run Version", "version", EmptyInputs));
        }

        private void AddCommandRow(TableLayoutPanel form, string commandId, string buttonText, Func<Dictionary<string, string>> inputProvider)
        {
            int row = form.RowCount++;
            form.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));

            CommandDefinition command = CommandCatalog.Find(commandId);
            Label label = new Label();
            label.Text = command.Id;
            label.Dock = DockStyle.Fill;
            label.TextAlign = ContentAlignment.MiddleLeft;
            form.Controls.Add(label, 0, row);

            Label description = new Label();
            description.Text = command.Description;
            description.Dock = DockStyle.Fill;
            description.TextAlign = ContentAlignment.MiddleLeft;
            form.Controls.Add(description, 1, row);

            Button button = CommandButton(buttonText, commandId, inputProvider);
            button.Dock = DockStyle.Fill;
            form.Controls.Add(button, 2, row);
        }

        private void AddDeferredRow(TableLayoutPanel form, string commandId)
        {
            int row = form.RowCount++;
            form.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));

            CommandDefinition command = CommandCatalog.Find(commandId);
            Label label = new Label();
            label.Text = command.Id;
            label.Dock = DockStyle.Fill;
            label.TextAlign = ContentAlignment.MiddleLeft;
            form.Controls.Add(label, 0, row);

            Label reason = new Label();
            reason.Text = command.DeferredReason;
            reason.Dock = DockStyle.Fill;
            reason.TextAlign = ContentAlignment.MiddleLeft;
            form.Controls.Add(reason, 1, row);

            Button button = new Button();
            button.Text = "Deferred";
            button.Enabled = false;
            button.Dock = DockStyle.Fill;
            toolTip.SetToolTip(button, command.DeferredReason);
            form.Controls.Add(button, 2, row);
        }

        private TextBox AddTextInput(TableLayoutPanel form, string labelText, string placeholder)
        {
            int row = form.RowCount++;
            form.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));

            Label label = new Label();
            label.Text = labelText;
            label.Dock = DockStyle.Fill;
            label.TextAlign = ContentAlignment.MiddleLeft;
            form.Controls.Add(label, 0, row);

            TextBox textBox = new TextBox();
            textBox.Dock = DockStyle.Fill;
            textBox.Text = placeholder;
            form.Controls.Add(textBox, 1, row);

            Label filler = new Label();
            filler.Text = String.Empty;
            form.Controls.Add(filler, 2, row);

            return textBox;
        }

        private Button CommandButton(string text, string commandId, Func<Dictionary<string, string>> inputProvider)
        {
            CommandDefinition command = CommandCatalog.Find(commandId);
            Button button = new Button();
            button.Text = text;
            button.Width = 150;
            button.Height = 32;
            button.Tag = commandId;
            toolTip.SetToolTip(button, command.Id + " -> " + command.BackendId);
            button.Click += delegate
            {
                RunCommand(commandId, inputProvider());
            };
            return button;
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
                RenderMessage(result.ToDisplayText());
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

            string workspace = Environment.GetEnvironmentVariable("FACMAN_WORKSPACE");
            if (!String.IsNullOrWhiteSpace(workspace))
            {
                workspaceBox.Text = workspace;
            }
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

        private static Dictionary<string, string> EmptyInputs()
        {
            return new Dictionary<string, string>();
        }

        private static Dictionary<string, string> Inputs(params string[] keyValues)
        {
            Dictionary<string, string> inputs = new Dictionary<string, string>();
            for (int index = 0; index + 1 < keyValues.Length; index += 2)
            {
                inputs[keyValues[index]] = keyValues[index + 1];
            }
            return inputs;
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
