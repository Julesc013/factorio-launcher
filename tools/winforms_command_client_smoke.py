from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINFORMS_ROOT = ROOT / "apps" / "gui" / "windows" / "winforms"


def main() -> int:
    if os.name != "nt":
        print("winforms-command-client-smoke: skipped (requires Windows/.NET Framework)")
        return 0
    build_tool = resolve_build_tool()
    if build_tool is None:
        print("winforms-command-client-smoke: MSBuild or dotnet is not available", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="facman-winforms-smoke-") as tmp:
        tmp_path = Path(tmp)
        project = write_project(tmp_path)
        program = write_program(tmp_path)
        build = run_build(build_tool, project, tmp_path)
        if build.returncode != 0:
            print(build.stdout)
            print(build.stderr, file=sys.stderr)
            return build.returncode

        exe = tmp_path / "bin" / "Debug" / "WinFormsCommandClientSmoke.exe"
        run = subprocess.run(
            [str(exe), str(program.parent)],
            cwd=tmp_path,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if run.returncode != 0:
            print(run.stdout)
            print(run.stderr, file=sys.stderr)
            return run.returncode

    print("winforms-command-client-smoke: ok")
    return 0


def write_project(tmp_path: Path) -> Path:
    project = tmp_path / "WinFormsCommandClientSmoke.csproj"
    sources = [
        WINFORMS_ROOT / "CommandModels.cs",
        WINFORMS_ROOT / "CommandCatalog.cs",
        WINFORMS_ROOT / "CommandClient.cs",
        WINFORMS_ROOT / "CliProcessClient.cs",
    ]
    compile_items = "\n".join(
        f'    <Compile Include="{source}" Link="{source.name}" />'
        for source in sources
    )
    project.write_text(
        f"""<Project ToolsVersion="15.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <PropertyGroup>
    <Configuration Condition=" '$(Configuration)' == '' ">Debug</Configuration>
    <Platform Condition=" '$(Platform)' == '' ">AnyCPU</Platform>
    <OutputType>Exe</OutputType>
    <TargetFrameworkVersion>v4.8</TargetFrameworkVersion>
    <RootNamespace>FacMan.WinForms.CommandClientSmoke</RootNamespace>
    <AssemblyName>WinFormsCommandClientSmoke</AssemblyName>
  </PropertyGroup>
  <PropertyGroup Condition=" '$(Configuration)|$(Platform)' == 'Debug|AnyCPU' ">
    <OutputPath>bin\\Debug\\</OutputPath>
  </PropertyGroup>
  <PropertyGroup Condition=" '$(Configuration)|$(Platform)' == 'Release|AnyCPU' ">
    <OutputPath>bin\\Release\\</OutputPath>
  </PropertyGroup>
  <ItemGroup>
    <Reference Include="System" />
    <Reference Include="System.Web.Extensions" />
  </ItemGroup>
  <ItemGroup>
{compile_items}
    <Compile Include="Program.cs" />
  </ItemGroup>
  <Import Project="$(MSBuildToolsPath)\\Microsoft.CSharp.targets" />
</Project>
""",
        encoding="utf-8",
    )
    return project


def resolve_build_tool() -> str | None:
    for candidate in ["MSBuild.exe", "msbuild"]:
        path = shutil.which(candidate)
        if path is not None:
            return path
    dotnet = shutil.which("dotnet")
    if dotnet is not None:
        return dotnet
    return None


def run_build(build_tool: str, project: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    if Path(build_tool).name.lower().startswith("msbuild"):
        args = [build_tool, str(project), "/p:Configuration=Debug"]
    else:
        args = [build_tool, "build", str(project)]
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_program(tmp_path: Path) -> Path:
    program = tmp_path / "Program.cs"
    program.write_text(
        r"""using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using FacMan.WinForms;

namespace FacMan.WinForms.CommandClientSmoke
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            string root = args.Length > 0 ? args[0] : Path.GetTempPath();
            string fakeCli = Path.Combine(root, "facman.cmd");
            File.WriteAllText(
                fakeCli,
                "@echo off\r\n" +
                "echo {\"schema\":\"fake.facman.v1\",\"status\":\"ok\"}\r\n" +
                "exit /b 0\r\n");

            CommandClient client = new CommandClient();
            CommandResult success = client.ExecuteAsync(
                CommandCatalog.Find("product.inspect"),
                new Dictionary<string, string>(),
                root,
                fakeCli,
                CancellationToken.None).GetAwaiter().GetResult();
            Require(success.ExitCode == 0, "product.inspect should exit successfully");
            Require(success.Stdout.Contains("fake.facman.v1"), "product.inspect should render fake backend stdout");
            Require(!success.Refused, "product.inspect should not be a frontend refusal");

            CommandResult missingInput = client.ExecuteAsync(
                CommandCatalog.Find("installs.import"),
                new Dictionary<string, string>(),
                root,
                fakeCli,
                CancellationToken.None).GetAwaiter().GetResult();
            Require(missingInput.Refused, "missing installs.import input should refuse");
            Require(missingInput.RefusalCode == "winforms_input_required", "missing input refusal code should match");

            CommandResult deferred = client.ExecuteAsync(
                CommandCatalog.Find("run.execute"),
                new Dictionary<string, string>(),
                root,
                fakeCli,
                CancellationToken.None).GetAwaiter().GetResult();
            Require(deferred.Refused, "deferred command should refuse");
            Require(deferred.RefusalCode == "winforms_command_deferred", "deferred refusal code should match");
            Require(deferred.Stdout.Contains("common.refusal.v1"), "deferred command should render structured refusal");

            return 0;
        }

        private static void Require(bool condition, string message)
        {
            if (!condition)
            {
                throw new InvalidOperationException(message);
            }
        }
    }
}
""",
        encoding="utf-8",
    )
    return program


if __name__ == "__main__":
    raise SystemExit(main())
