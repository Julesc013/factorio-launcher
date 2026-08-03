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
    print("winforms-c1-runtime-smoke: ok (5 states, pages, refusal, Last Run, recovery)")
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
using System.Reflection;
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
                Require(form.AutoScaleMode == AutoScaleMode.Dpi, "DPI autoscaling required");
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
                RequireNamedInteractiveControls(form);
            }
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
                if (child.Enabled && child.TabStop && (child is Button || child is ComboBox || child is ListView || child is TabControl))
                    Require(!String.IsNullOrWhiteSpace(child.AccessibleName), "interactive control needs accessible name: " + child.GetType().Name);
                RequireNamedInteractiveControls(child);
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
