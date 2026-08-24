# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

param(
    [Parameter(Mandatory = $true)]
    [string]$Manifest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-Digest([string]$Path, [string]$Expected, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label is absent"
    }
    $actual = Get-Sha256 $Path
    if ($actual -ne $Expected) {
        throw "$Label digest mismatch"
    }
}

function Expand-SafeZip([string]$Archive, [string]$Destination) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Directory]::CreateDirectory($Destination) | Out-Null
    $root = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            if ([string]::IsNullOrWhiteSpace($name) -or $name.Contains('\') -or
                [System.IO.Path]::IsPathRooted($name) -or $name.Contains(':')) {
                throw "unsafe ZIP path"
            }
            $segments = $name.Split('/')
            if ($segments -contains '..' -or $segments -contains '.') {
                throw "unsafe ZIP traversal"
            }
            if (-not $seen.Add($name)) {
                throw "duplicate or case-colliding ZIP path"
            }
            $unixType = (($entry.ExternalAttributes -shr 16) -band 0xF000)
            if ($unixType -eq 0xA000 -or ($entry.ExternalAttributes -band 0x400) -ne 0) {
                throw "ZIP link or reparse entry refused"
            }
            $target = [System.IO.Path]::GetFullPath((Join-Path $Destination $name))
            if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
                throw "ZIP destination escaped task root"
            }
            if ([string]::IsNullOrEmpty($entry.Name)) {
                [System.IO.Directory]::CreateDirectory($target) | Out-Null
            } else {
                [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($target)) | Out-Null
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
            }
        }
    } finally {
        $zip.Dispose()
    }
}

function Invoke-Required([string]$Name, [string]$Executable, [string[]]$Arguments) {
    $output = & $Executable @Arguments 2>&1 | Out-String
    $code = $LASTEXITCODE
    $receipt = [ordered]@{ name = $Name; exit_code = $code; output = $output.Trim() }
    $script:result.commands += $receipt
    if ($code -ne 0) {
        throw "$Name failed with exit code $code"
    }
}

$configuration = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$evidenceRoot = [string]$configuration.evidence_path
$resultPath = Join-Path $evidenceRoot 'private-route-result.v1.json'
$taskRoot = 'C:\FacManPrivateRouteTask'
$result = [ordered]@{
    schema = 'facman.private_route_result.v1'
    status = 'running'
    route_id = [string]$configuration.route_id
    classification = 'local_private_input_engineering_only'
    networking = 'disabled'
    private_archive_uploaded = $false
    private_archive_packaged = $false
    commands = @()
}

try {
    if (Test-Path -LiteralPath $taskRoot) {
        throw 'task root already exists'
    }
    [System.IO.Directory]::CreateDirectory($taskRoot) | Out-Null
    [System.IO.Directory]::CreateDirectory($evidenceRoot) | Out-Null

    Assert-Digest $configuration.candidate_path $configuration.candidate.sha256 'candidate'
    Assert-Digest $configuration.private_archive_path $configuration.private_archive.sha256 'private archive'
    Assert-Digest $configuration.harness_path $configuration.engineering_harness.sha256 'engineering harness'
    Assert-Digest $configuration.route_record_path $configuration.route_record.sha256 'route record'

    $candidateRoot = Join-Path $taskRoot 'candidate'
    $factorioExtract = Join-Path $taskRoot 'factorio'
    Expand-SafeZip $configuration.candidate_path $candidateRoot
    Expand-SafeZip $configuration.private_archive_path $factorioExtract

    $facman = Join-Path $candidateRoot 'bin\facman.exe'
    if (-not (Test-Path -LiteralPath $facman -PathType Leaf)) {
        throw 'candidate facman.exe is absent'
    }
    $matches = @(Get-ChildItem -LiteralPath $factorioExtract -Recurse -Filter factorio.exe -File)
    if ($matches.Count -ne 1) {
        throw 'private archive must contain exactly one factorio.exe'
    }
    $factorio = $matches[0].FullName
    Assert-Digest $factorio $configuration.factorio_executable.sha256 'Factorio executable'
    $sourceRoot = $matches[0].Directory.Parent.Parent.FullName

    $workspace = Join-Path $taskRoot 'workspace'
    $profileRoot = Join-Path $taskRoot 'profile'
    $tempRoot = Join-Path $taskRoot 'temp'
    $taskEvidenceRoot = Join-Path $taskRoot 'evidence'
    $taskRouteRecord = Join-Path $taskRoot 'route-record.toml'
    $roamingRoot = Join-Path $profileRoot 'AppData\Roaming'
    $localRoot = Join-Path $profileRoot 'AppData\Local'
    foreach ($directory in @($workspace, $profileRoot, $tempRoot, $taskEvidenceRoot, $roamingRoot, $localRoot)) {
        [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    }
    Copy-Item -LiteralPath $configuration.route_record_path -Destination $taskRouteRecord
    Assert-Digest $taskRouteRecord $configuration.route_record.sha256 'task route record'
    $env:APPDATA = $roamingRoot
    $env:LOCALAPPDATA = $localRoot
    $env:USERPROFILE = $profileRoot
    $env:TEMP = $tempRoot
    $env:TMP = $tempRoot
    $env:PATH = ''

    Invoke-Required 'package_verify' $facman @('package', 'verify', '--json')
    Invoke-Required 'product_inspect' $facman @('product', 'inspect', '--json')
    Invoke-Required 'doctor' $facman @('--workspace', $workspace, 'doctor', '--json')
    Invoke-Required 'tui_routes' $facman @('tui', '--list', '--json')
    Invoke-Required 'install_import' $facman @(
        '--workspace', $workspace, 'installs', 'import', $sourceRoot,
        '--id', 'factorio-2-1-14-isolated', '--json'
    )
    Invoke-Required 'instance_create' $facman @(
        '--workspace', $workspace, 'instances', 'create', 'Factorio 2.1.14 Engineering',
        '--install', 'factorio-2-1-14-isolated', '--json'
    )

    $instanceId = 'factorio-2-1-14-engineering'
    $instanceRoot = Join-Path $workspace "instances\$instanceId"
    $config = Join-Path $instanceRoot 'config\config.ini'
    $mods = Join-Path $instanceRoot 'mods'
    $harnessAcknowledgement = if ($configuration.PSObject.Properties.Name -contains 'harness_acknowledgement') {
        [string]$configuration.harness_acknowledgement
    } else {
        'TEST-HARNESS-NO-REAL-RELEASE-AUTHORITY'
    }
    foreach ($journey in @('launch', 'relaunch')) {
        # The native harness deliberately accepts only task-root descendants.
        # Export the completed receipt to the writable host mapping afterwards.
        $playResult = Join-Path $taskEvidenceRoot "engineering-$journey.v1.json"
        Invoke-Required "engineering_$journey" $configuration.harness_path @(
            '--task-root', $taskRoot,
            '--workspace', $workspace,
            '--source-root', $sourceRoot,
            '--instance-root', $instanceRoot,
            '--executable', $factorio,
            '--route-record', $taskRouteRecord,
            '--config', $config,
            '--mod-directory', $mods,
            '--result-file', $playResult,
            '--instance-id', $instanceId,
            '--acknowledge', $harnessAcknowledgement,
            '--close-after-seconds', '20',
            '--timeout-seconds', '90'
        )
        $play = Get-Content -LiteralPath $playResult -Raw | ConvertFrom-Json
        if ($play.status -ne 'completed' -or
            $play.session.operation_outcome -ne 'completed' -or
            $play.last_run.terminal_result.outcome -ne 'completed' -or
            -not $play.session.authoritative_last_run_recorded -or
            -not $play.source_inventory.unchanged) {
            throw "$journey did not produce one completed truthful outcome"
        }
        Copy-Item -LiteralPath $playResult -Destination (Join-Path $evidenceRoot "engineering-$journey.v1.json")
    }

    Assert-Digest $configuration.candidate_path $configuration.candidate.sha256 'candidate after replay'
    Assert-Digest $configuration.private_archive_path $configuration.private_archive.sha256 'private archive after replay'
    $result.status = 'passed'
} catch {
    $result.status = 'failed'
    $result.error = $_.Exception.Message
} finally {
    if (Test-Path -LiteralPath $taskRoot) {
        Remove-Item -LiteralPath $taskRoot -Recurse -Force
    }
    $result.task_root_removed = -not (Test-Path -LiteralPath $taskRoot)
    $result.completed_utc = [DateTime]::UtcNow.ToString('o')
    $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $resultPath -Encoding UTF8
}

if ($result.status -ne 'passed') {
    exit 1
}
