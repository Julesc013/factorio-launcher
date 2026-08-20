# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Compile and execute the deterministic WinForms C1 renderer on Windows."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "apps/gui/windows/winforms/FacMan.WinForms.csproj"


def main() -> int:
    if os.name != "nt":
        print("winforms-c1-runtime-smoke: skipped (requires Windows/.NET Framework)")
        return 0
    build_tool = resolve_build_tool()
    if build_tool is None:
        print("winforms-c1-runtime-smoke: MSBuild or dotnet is not available", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="facman-winforms-c1-smoke-") as raw:
        root = Path(raw)
        project = write_project(root)
        write_program(root)
        result = run_build(build_tool, project, root)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode
        executable = root / "bin/Debug/FacMan.WinForms.C1Smoke.exe"
        result = subprocess.run(
            [str(executable)], cwd=root, check=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode
    print(
        "winforms-c1-runtime-smoke: ok "
        "(states, keyboard, UIA, system colours, minimum layout, 100-200% scale)"
    )
    return 0


def resolve_build_tool() -> str | None:
    for candidate in ("MSBuild.exe", "msbuild"):
        path = shutil.which(candidate)
        if path:
            return path
    return shutil.which("dotnet")


def run_build(build_tool: str, project: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    if Path(build_tool).name.lower().startswith("msbuild"):
        args = [build_tool, str(project), "/p:Configuration=Debug", "/p:Platform=x64"]
    else:
        args = [build_tool, "msbuild", str(project), "/p:Configuration=Debug", "/p:Platform=x64"]
    return subprocess.run(
        args, cwd=cwd, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def write_project(root: Path) -> Path:
    project = root / "FacMan.WinForms.C1Smoke.csproj"
    project.write_text(
        f"""<Project ToolsVersion="15.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup>
    <Configuration Condition=" '$(Configuration)' == '' ">Debug</Configuration>
    <Platform Condition=" '$(Platform)' == '' ">x64</Platform>
    <OutputType>Exe</OutputType>
    <TargetFrameworkVersion>v4.8</TargetFrameworkVersion>
    <RootNamespace>FacMan.WinForms.C1Smoke</RootNamespace>
    <AssemblyName>FacMan.WinForms.C1Smoke</AssemblyName>
    <PlatformTarget>x64</PlatformTarget>
  </PropertyGroup>
  <PropertyGroup Condition=" '$(Configuration)|$(Platform)' == 'Debug|x64' ">
    <OutputPath>bin\\Debug\\</OutputPath>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="System" />
    <Reference Include="System.Drawing" />
    <Reference Include="System.Windows.Forms" />
    <Reference Include="UIAutomationClient" />
    <Reference Include="UIAutomationTypes" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="{PROJECT}"><Name>FacMan.WinForms</Name></ProjectReference>
    <Compile Include="Program.cs" />
  </ItemGroup>
  <Import Project="$(MSBuildToolsPath)\\Microsoft.CSharp.targets" />
</Project>
""",
        encoding="utf-8",
    )
    return project


def write_program(root: Path) -> None:
    (root / "Program.cs").write_text(
        r"""using System;
using System.Collections.Generic;
using System.Drawing;
using System.Reflection;
using System.Windows.Automation;
using System.Windows.Forms;
using FacMan.WinForms;

namespace FacMan.WinForms.C1Smoke
{
    internal static class Program
    {
        [STAThread]
        private static int Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Environment.SetEnvironmentVariable("FACMAN_PRESENTATION_MODE", "evidence");
            C1FixturePresentationStore store = new C1FixturePresentationStore();
            Require(store.States.Count == 5, "five fixture states required");
            Require(store.Select("refused").Text("refusal", "code") == "stale_readiness", "exact stale refusal required");
            Require(store.Apply("instance.play").FixtureState == "refused", "refused Play must not transition");
            Require(store.Apply("instance.readiness.refresh").FixtureState == "positive", "rescan returns ready without launch");
            Require(store.Apply("instance.play").FixtureState == "running", "fixture Play reaches running");
            Require(store.Select("exited").Text("launch_deck", "last_run", "outcome") == "exited", "Last Run required");
            Require(store.Apply("instance.play").FixtureState == "running", "exited state must relaunch");
            Require(store.Select("interrupted").Text("recovery", "state") == "required", "recovery state required");
            Require(store.Apply("recovery.apply").FixtureState == "positive", "recovery must not auto-launch");
            using (C1ShellForm form = new C1ShellForm())
            {
                form.CreateControl();
                form.Show();
                Application.DoEvents();
                Require(form.AutoScaleMode == AutoScaleMode.Dpi, "DPI autoscaling required");
                Require(form.MinimumSize.Width >= 960 && form.MinimumSize.Height >= 640, "minimum usable window required");
                Require(!String.IsNullOrWhiteSpace(form.AccessibleName), "form accessible name required");
                TabControl pages = Field<TabControl>(form, "pages");
                Require(pages.TabPages.Count == 5, "four pages plus Advanced required");
                string[] names = { "Instances", "Installations", "Activity", "Settings / About", "Advanced" };
                for (int index = 0; index < names.Length; ++index)
                    Require(pages.TabPages[index].Text == names[index], names[index] + " page required");
                MethodInfo select = typeof(C1ShellForm).GetMethod("SelectEvidenceState", BindingFlags.Instance | BindingFlags.NonPublic);
                select.Invoke(form, new object[] { "refused" });
                Require(Field<TextBox>(form, "refusalDetail").Text.Contains("stale_readiness"), "refusal must render");
                select.Invoke(form, new object[] { "running" });
                Require(Field<ListView>(form, "activityList").Items.Count == 1, "running operation must render");
                select.Invoke(form, new object[] { "exited" });
                Require(Field<Label>(form, "deckLastRun").Text.Contains("exited"), "Last Run must render");
                select.Invoke(form, new object[] { "interrupted" });
                Require(Field<Label>(form, "deckRefusal").Text.Contains("recovery.fixture-play-001"), "recovery identity must render");
                Require(Field<FlowLayoutPanel>(form, "activityActions").Controls.Count == 2, "inspect and recover actions required");
                select.Invoke(form, new object[] { "refused" });
                RequireSystemColourContract(form);
                select.Invoke(form, new object[] { "positive" });
                RequireNamedInteractiveControls(form);
                RequireUiAutomationProvider(form);
                RequireKeyboardContract(form);
                RequireMinimumLayout(form);
                RequireLongUnicodeProjection(form);
                form.Close();
            }
            foreach (float scale in new float[] { 1.00F, 1.25F, 1.50F, 1.75F, 2.00F })
                RequireScaledLayout(scale);
            return 0;
        }

        private static T Field<T>(object target, string name) where T : class
        {
            return typeof(C1ShellForm).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic).GetValue(target) as T;
        }

        private static void RequireNamedInteractiveControls(Control parent)
        {
            foreach (Control child in parent.Controls)
            {
                bool interactive = child is ButtonBase || child is ComboBox ||
                    child is ListView || child is TabControl || child is TextBox;
                if (child.Enabled && child.TabStop && interactive)
                {
                    Require(!String.IsNullOrWhiteSpace(child.AccessibleName), "interactive control needs accessible name: " + child.GetType().Name);
                    Require(child.AccessibilityObject.Role != AccessibleRole.None,
                        "interactive control needs an accessibility role: " + child.AccessibleName);
                    ButtonBase button = child as ButtonBase;
                    if (button != null && child.Visible)
                        Require(button.Text.Contains("&"), "visible action needs a keyboard mnemonic: " + child.AccessibleName);
                }
                RequireNamedInteractiveControls(child);
            }
        }

        private static void RequireKeyboardContract(C1ShellForm form)
        {
            MenuStrip menu = form.MainMenuStrip;
            Require(menu != null && menu.Items.Count >= 2, "application menus required");
            foreach (ToolStripItem item in menu.Items)
                Require(item.Text.Contains("&"), "top-level menu needs an access key: " + item.Text);

            ToolStripMenuItem navigate = menu.Items[0] as ToolStripMenuItem;
            Require(navigate != null, "Navigate menu required");
            HashSet<Keys> shortcuts = new HashSet<Keys>();
            foreach (ToolStripItem item in navigate.DropDownItems)
            {
                ToolStripMenuItem command = item as ToolStripMenuItem;
                if (command == null) continue;
                Require(command.Text.Contains("&"), "navigation item needs an access key: " + command.Text);
                shortcuts.Add(command.ShortcutKeys);
            }
            foreach (Keys expected in new Keys[] {
                Keys.Control | Keys.D1, Keys.Control | Keys.D2,
                Keys.Control | Keys.D3, Keys.Control | Keys.D4,
                Keys.Control | Keys.D5 })
                Require(shortcuts.Contains(expected), "missing page keyboard shortcut: " + expected);

            int focusable = 0;
            foreach (Control control in Descendants(form))
            {
                if (!control.Visible || !control.Enabled || !control.TabStop || !control.CanSelect)
                    continue;
                if (!(control is ButtonBase || control is ComboBox ||
                    control is ListView || control is TabControl || control is TextBox))
                    continue;
                Require(control.Focus(), "keyboard focus could not enter: " + control.AccessibleName);
                Application.DoEvents();
                Require(control.ContainsFocus, "visible focus target was not retained: " + control.AccessibleName);
                ++focusable;
            }
            Require(focusable >= 4, "ordinary page and Launch Deck need at least four keyboard focus targets");
        }

        private static void RequireUiAutomationProvider(C1ShellForm form)
        {
            AutomationElement root = AutomationElement.FromHandle(form.Handle);
            Require(root != null, "UI Automation must expose the product window");
            Require(root.Current.ControlType == ControlType.Window,
                "UI Automation root must be a window");
            Require(root.Current.Name == form.AccessibleName,
                "UI Automation window name must match the product accessible name");

            RequireAutomationElement(root, ControlType.Tab, "FacMan product pages");
            RequireAutomationElement(
                root,
                new ControlType[] { ControlType.List, ControlType.DataGrid },
                "Instances");
            RequireAutomationElement(root, ControlType.Button, "Play");
            RequireAutomationElement(root, ControlType.Button, "Rescan readiness");

            AutomationElementCollection elements = root.FindAll(
                TreeScope.Descendants,
                new PropertyCondition(AutomationElement.IsControlElementProperty, true));
            int namedFocusable = 0;
            foreach (AutomationElement element in elements)
            {
                if (element.Current.IsKeyboardFocusable)
                {
                    Require(!String.IsNullOrWhiteSpace(element.Current.Name),
                        "UI Automation keyboard target needs a name: " + element.Current.ControlType.ProgrammaticName);
                    ++namedFocusable;
                }
            }
            Require(namedFocusable >= 4,
                "UI Automation must expose the ordinary page and Launch Deck keyboard targets");
        }

        private static void RequireAutomationElement(
            AutomationElement root,
            ControlType type,
            string name)
        {
            RequireAutomationElement(root, new ControlType[] { type }, name);
        }

        private static void RequireAutomationElement(
            AutomationElement root,
            ControlType[] types,
            string name)
        {
            List<Condition> typeConditions = new List<Condition>();
            foreach (ControlType type in types)
                typeConditions.Add(new PropertyCondition(
                    AutomationElement.ControlTypeProperty, type));
            Condition typeCondition = typeConditions.Count == 1
                ? typeConditions[0]
                : (Condition)new OrCondition(typeConditions.ToArray());
            AndCondition condition = new AndCondition(
                typeCondition,
                new PropertyCondition(AutomationElement.NameProperty, name));
            Require(root.FindFirst(TreeScope.Descendants, condition) != null,
                "UI Automation element is missing: " + name);
        }

        private static void RequireSystemColourContract(C1ShellForm form)
        {
            TextBox refusal = Field<TextBox>(form, "refusalDetail");
            Require(refusal.BackColor.ToArgb() == SystemColors.Info.ToArgb(),
                "refusal background must follow the Windows system palette");
            Require(refusal.ForeColor.ToArgb() == SystemColors.InfoText.ToArgb(),
                "refusal foreground must follow the Windows system palette");
            Require(Field<Label>(form, "deckRefusal").ForeColor.ToArgb() == SystemColors.ControlText.ToArgb(),
                "Launch Deck status must follow the Windows system palette");
            Require(Field<Label>(form, "deckSourceNotice").ForeColor.ToArgb() == SystemColors.GrayText.ToArgb(),
                "authority notice must follow the Windows system palette");
        }

        private static void RequireMinimumLayout(C1ShellForm form)
        {
            form.Size = form.MinimumSize;
            form.PerformLayout();
            Application.DoEvents();
            Require(Field<TabControl>(form, "pages").ClientSize.Width > 0, "pages must remain visible at minimum size");
            Require(Field<TabControl>(form, "pages").ClientSize.Height > 0, "pages must remain usable at minimum size");
            Require(Field<Button>(form, "primaryAction").Bounds.Width >= 140, "primary action minimum width required");
            Require(Field<Button>(form, "primaryAction").Bounds.Height >= 36, "primary action minimum height required");
        }

        private static void RequireLongUnicodeProjection(C1ShellForm form)
        {
            Label target = Field<Label>(form, "deckInstance");
            string value = "Selected instance: 工場 e\u0301 🚂 — " + new String('L', 240) + @"\portable\very long path";
            target.Text = value;
            form.PerformLayout();
            Require(target.Text == value, "long Unicode product identity must not be rewritten by the frontend");
            Require(target.Bounds.Width > 0 && target.Bounds.Height > 0, "long Unicode product identity needs a visible layout box");
        }

        private static void RequireScaledLayout(float scale)
        {
            using (C1ShellForm form = new C1ShellForm())
            {
                form.CreateControl();
                form.Scale(new SizeF(scale, scale));
                form.PerformLayout();
                Require(form.AutoScaleMode == AutoScaleMode.Dpi, "DPI autoscaling must survive " + scale);
                Require(Field<TabControl>(form, "pages").Bounds.Width > 0, "scaled pages width required at " + scale);
                Require(Field<TabControl>(form, "pages").Bounds.Height > 0, "scaled pages height required at " + scale);
                Require(Field<Button>(form, "primaryAction").Bounds.Width > 0, "scaled primary action required at " + scale);
                Require(Field<Label>(form, "deckLastRun").Bounds.Height > 0, "scaled Last Run required at " + scale);
            }
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
            if (!condition) throw new InvalidOperationException(message);
        }
    }
}
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
