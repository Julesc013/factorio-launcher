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

function Assert-ExactProperties($Value, [string[]]$Expected, [string]$Label) {
    $actual = @($Value.PSObject.Properties.Name | Sort-Object)
    $wanted = @($Expected | Sort-Object)
    if (($actual -join "`n") -ne ($wanted -join "`n")) {
        throw "$Label has missing, duplicate, or unknown fields"
    }
}

function Wait-RoutePermit(
    [string]$PermitRoot,
    $Slot,
    [string]$TaskRoot,
    [string]$EvidenceRoot
) {
    $ordinal = [int]$Slot.launch_ordinal
    $readyPath = Join-Path $PermitRoot "launch-$ordinal.ready.v2.json"
    for ($attempt = 0; $attempt -lt 600; $attempt++) {
        if (Test-Path -LiteralPath $readyPath -PathType Leaf) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path -LiteralPath $readyPath -PathType Leaf)) {
        throw "launch $ordinal permit ready record was not supplied by the host handshake"
    }
    $ready = Get-Content -LiteralPath $readyPath -Raw | ConvertFrom-Json
    Assert-ExactProperties $ready @(
        'schema', 'route_id', 'launch_ordinal', 'operation_id', 'attempt_id', 'action',
        'envelope_sha256', 'session_custody_sha256', 'host_freshness_sha256',
        'issue_receipt_sha256'
    ) "launch $ordinal permit ready record"
    if ($ready.schema -ne 'facman.route_permit_ready.v2' -or
        [string]$ready.route_id -ne [string]$configuration.route_id -or
        [int]$ready.launch_ordinal -ne $ordinal -or
        [string]$ready.operation_id -ne [string]$Slot.operation_id -or
        [string]$ready.attempt_id -ne [string]$Slot.attempt_id -or
        [string]$ready.action -ne [string]$Slot.action) {
        throw "launch $ordinal permit ready record changed the frozen slot"
    }
    foreach ($name in @(
        'envelope_sha256', 'session_custody_sha256', 'host_freshness_sha256',
        'issue_receipt_sha256'
    )) {
        if ([string]$ready.$name -cnotmatch '^[0-9a-f]{64}$') {
            throw "launch $ordinal permit ready digest is invalid"
        }
    }

    $source = [ordered]@{
        envelope = Join-Path $PermitRoot "launch-$ordinal.envelope.json"
        session = Join-Path $PermitRoot "launch-$ordinal.session-custody.json"
        freshness = Join-Path $PermitRoot "launch-$ordinal.host-freshness.v2.json"
        issue = Join-Path $PermitRoot "launch-$ordinal.issue-receipt.v2.json"
    }
    Assert-Digest $source.envelope $ready.envelope_sha256 "launch $ordinal permit envelope"
    Assert-Digest $source.session $ready.session_custody_sha256 "launch $ordinal session custody"
    Assert-Digest $source.freshness $ready.host_freshness_sha256 "launch $ordinal host freshness"
    Assert-Digest $source.issue $ready.issue_receipt_sha256 "launch $ordinal issue receipt"

    $custodyRoot = Join-Path $TaskRoot "permit\launch-$ordinal"
    [System.IO.Directory]::CreateDirectory($custodyRoot) | Out-Null
    $destination = [ordered]@{
        envelope = Join-Path $custodyRoot 'envelope.json'
        session = Join-Path $custodyRoot 'session-custody.json'
        freshness = Join-Path $custodyRoot 'host-freshness.json'
    }
    Copy-Item -LiteralPath $source.envelope -Destination $destination.envelope
    Copy-Item -LiteralPath $source.session -Destination $destination.session
    Copy-Item -LiteralPath $source.freshness -Destination $destination.freshness
    Copy-Item -LiteralPath $source.issue -Destination (
        Join-Path $EvidenceRoot "permit-issue-launch-$ordinal.v2.json")
    Assert-Digest $destination.envelope $ready.envelope_sha256 "task permit envelope"
    Assert-Digest $destination.session $ready.session_custody_sha256 "task session custody"
    Assert-Digest $destination.freshness $ready.host_freshness_sha256 "task host freshness"
    return [pscustomobject]@{
        envelope = $destination.envelope
        envelope_sha256 = [string]$ready.envelope_sha256
        session = $destination.session
        freshness = $destination.freshness
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

function Invoke-Required(
    [string]$Name,
    [string]$Executable,
    [string[]]$Arguments,
    [string]$ResultFile = '',
    [string]$ResultDestination = '',
    [hashtable]$EvidenceCopies = @{}
) {
    $output = & $Executable @Arguments 2>&1 | Out-String
    $code = $LASTEXITCODE
    $receipt = [ordered]@{ name = $Name; exit_code = $code; output = $output.Trim() }
    $script:result.commands += $receipt
    if (-not [string]::IsNullOrEmpty($ResultFile) -and
        -not [string]::IsNullOrEmpty($ResultDestination) -and
        (Test-Path -LiteralPath $ResultFile -PathType Leaf)) {
        Copy-Item -LiteralPath $ResultFile -Destination $ResultDestination
    }
    foreach ($source in $EvidenceCopies.Keys) {
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            Copy-Item -LiteralPath $source -Destination $EvidenceCopies[$source]
        }
    }
    if ($code -ne 0) {
        throw "$Name failed with exit code $code"
    }
}

$configuration = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
Assert-ExactProperties $configuration.permit_protocol @(
    'schema', 'topology', 'maximum_ttl_seconds', 'preissue_both_permits', 'slots'
) 'permit protocol'
if ($configuration.schema -ne 'facman.private_route_guest_manifest.v3' -or
    $configuration.networking -ne 'disabled' -or
    $configuration.permit_protocol.schema -ne 'facman.route_permit_two_phase.v2' -or
    $configuration.permit_protocol.topology -ne 'host_guest_evidence_handshake' -or
    [int]$configuration.permit_protocol.maximum_ttl_seconds -ne 120 -or
    [bool]$configuration.permit_protocol.preissue_both_permits -or
    @($configuration.permit_protocol.slots).Count -ne 2) {
    throw 'guest manifest does not describe the frozen two-phase permit topology'
}
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
    Assert-Digest $configuration.candidate_record_path $configuration.candidate_record.sha256 'candidate record'
    Assert-Digest $configuration.private_archive_path $configuration.private_archive.sha256 'private archive'
    Assert-Digest $configuration.harness_path $configuration.engineering_harness.sha256 'engineering harness'
    Assert-Digest $configuration.route_record_path $configuration.route_record.sha256 'route record'
    Assert-Digest $configuration.guest_runner_path $configuration.guest_runner.sha256 'guest runner'
    Assert-Digest $configuration.bundle_builder_path $configuration.bundle_builder.sha256 'bundle builder'
    Assert-Digest $configuration.sandbox_configuration_path $configuration.sandbox_configuration.sha256 'sandbox configuration'
    foreach ($earlySecondPermit in @(
        'launch-2.ready.v2.json', 'launch-2.envelope.json',
        'launch-2.session-custody.json', 'launch-2.host-freshness.v2.json',
        'launch-2.issue-receipt.v2.json'
    )) {
        if (Test-Path -LiteralPath (Join-Path $configuration.permit_path $earlySecondPermit)) {
            throw 'second permit was preissued before first-launch terminal evidence'
        }
    }

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
    $permitClaimRoot = Join-Path $taskEvidenceRoot 'permit-claims'
    $taskRouteRecord = Join-Path $taskRoot 'route-record.toml'
    $roamingRoot = Join-Path $profileRoot 'AppData\Roaming'
    $localRoot = Join-Path $profileRoot 'AppData\Local'
    foreach ($directory in @($workspace, $profileRoot, $tempRoot, $taskEvidenceRoot, $permitClaimRoot, $roamingRoot, $localRoot)) {
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
        $ordinal = if ($journey -eq 'launch') { 1 } else { 2 }
        $slot = @($configuration.permit_protocol.slots | Where-Object {
            [int]$_.launch_ordinal -eq $ordinal
        })
        if ($slot.Count -ne 1) { throw "launch $ordinal permit slot is not unique" }
        $permit = Wait-RoutePermit $configuration.permit_path $slot[0] $taskRoot $evidenceRoot
        # The native harness deliberately accepts only task-root descendants.
        # Export any materialized receipt before propagating success or failure.
        $playResult = Join-Path $taskEvidenceRoot "engineering-$journey.v1.json"
        $playDestination = Join-Path $evidenceRoot "engineering-$journey.v1.json"
        $permitConsume = Join-Path $taskEvidenceRoot "permit-consume-$journey.v1.json"
        $permitRefusal = Join-Path $taskEvidenceRoot "permit-refusal-$journey.v1.json"
        $permitEvidenceCopies = @{
            $permitConsume = Join-Path $evidenceRoot "permit-consume-$journey.v1.json"
            $permitRefusal = Join-Path $evidenceRoot "permit-refusal-$journey.v1.json"
        }
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
            '--candidate-package', $configuration.candidate_path,
            '--private-archive', $configuration.private_archive_path,
            '--guest-runner', $configuration.guest_runner_path,
            '--bundle-builder', $configuration.bundle_builder_path,
            '--sandbox-configuration', $configuration.sandbox_configuration_path,
            '--host-freshness', $permit.freshness,
            '--permit-envelope', $permit.envelope,
            '--permit-envelope-sha256', $permit.envelope_sha256,
            '--permit-session-custody', $permit.session,
            '--permit-claim-directory', $permitClaimRoot,
            '--permit-consume-receipt', $permitConsume,
            '--permit-refusal-receipt', $permitRefusal,
            '--launch-ordinal', [string]$ordinal,
            '--launch-action', [string]$slot[0].action,
            '--operation-id', [string]$slot[0].operation_id,
            '--attempt-id', [string]$slot[0].attempt_id,
            '--acknowledge', $harnessAcknowledgement,
            '--close-after-seconds', '90',
            '--timeout-seconds', '180'
        ) -ResultFile $playResult -ResultDestination $playDestination -EvidenceCopies $permitEvidenceCopies
        $play = Get-Content -LiteralPath $playResult -Raw | ConvertFrom-Json
        if ($play.status -ne 'completed' -or
            $play.session.operation_outcome -ne 'completed' -or
            $play.last_run.terminal_result.outcome -ne 'completed' -or
            -not $play.session.authoritative_last_run_recorded -or
            -not $play.source_inventory.unchanged) {
            throw "$journey did not produce one completed truthful outcome"
        }
        if ($ordinal -eq 1) {
            $terminal = [ordered]@{
                schema = 'facman.route_first_terminal_ready.v2'
                route_id = [string]$configuration.route_id
                launch_ordinal = 1
                operation_id = [string]$slot[0].operation_id
                attempt_id = [string]$slot[0].attempt_id
                terminal_receipt_sha256 = Get-Sha256 $playResult
                safety_revalidation_required_before_second_issue = $true
            }
            $terminal | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (
                Join-Path $evidenceRoot 'launch-1-terminal-ready-for-second-permit.v2.json') -Encoding UTF8
        }
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
