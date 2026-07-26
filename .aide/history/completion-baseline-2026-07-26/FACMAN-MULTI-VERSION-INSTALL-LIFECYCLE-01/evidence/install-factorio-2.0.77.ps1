# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$facOperationId = 'factorio-2.0.77-20260720-105833'
$facLibraryRoot = 'D:\Games\Factorio'
$facTarget = 'D:\Games\Factorio\2.0'
$facRollbackParent = 'D:\Games\Factorio\.facman-rollback'
$facRollback = 'D:\Games\Factorio\.facman-rollback\2.0-portable-pre-official-20260720-105833'
$facFailedParent = 'D:\Games\Factorio\.facman-failed'
$facFailed = 'D:\Games\Factorio\.facman-failed\2.0-official-failed-20260720-105833'
$facOperationRoot = 'D:\Games\Factorio\.facman-operations\factorio-2.0.77-20260720-105833'
$facInstallerRoot = 'E:\Downloads\FacMan-Setup-FactorioSpaceAge-2.0.77'
$facInstaller = 'E:\Downloads\FacMan-Setup-FactorioSpaceAge-2.0.77\Setup_FactorioSpaceAge_2.0.77.exe'
$facInstallerLog = Join-Path $facOperationRoot 'installer.log'
$facRegistrySnapshot = Join-Path $facOperationRoot 'factorio-space-age-2.1-uninstall.reg'
$facResultPath = Join-Path $facOperationRoot 'result.json'
$facRegistryKey = 'HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\Factorio Space Age_is1'
$facRegistryPsPath = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Factorio Space Age_is1'

$facExpectedHashes = [ordered]@{
    'Setup_FactorioSpaceAge_2.0.77.exe' = '3BC6B4A411E2D9CBE6EC791BAB95430A54242EDAACD29F2D1D97EBFC3450ECA2'
    'Setup_FactorioSpaceAge_2.0.77-1.bin' = 'DD676EFB7E411321C33AB1CEF9F897920769AB08B1A47A23C974C6D0842B5AB1'
    'Setup_FactorioSpaceAge_2.0.77-2.bin' = 'C8C82BBD394BE9B4CD6965D082363BA5238FD79AAC223AC7197D0D10C8E5544F'
    'Setup_FactorioSpaceAge_2.0.77-3.bin' = '8E80F56EB881EB1B76FF0FF8EA1AF7DAEF6B3FB3F661EAB982500B9C550FEBE1'
}

function Write-FacResult {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Detail,
        [Nullable[int]]$InstallerExitCode = $null
    )

    $facResult = [ordered]@{
        schema = 'facman.local_install_operation.v1'
        operation_id = $facOperationId
        status = $Status
        detail = $Detail
        installer_exit_code = $InstallerExitCode
        target = $facTarget
        retained_rollback = $facRollback
        failed_tree = if (Test-Path -LiteralPath $facFailed) { $facFailed } else { $null }
        registry_snapshot = $facRegistrySnapshot
        installer_log = $facInstallerLog
        completed_at = (Get-Date).ToUniversalTime().ToString('o')
    }
    $facResult | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $facResultPath -Encoding utf8
}

function Restore-FacRegistry {
    if (Test-Path -LiteralPath $facRegistrySnapshot -PathType Leaf) {
        & reg.exe import $facRegistrySnapshot | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Exact 2.1 uninstall-key restoration failed with reg.exe exit $LASTEXITCODE"
        }
    }
}

function Restore-FacTarget {
    if (Test-Path -LiteralPath $facTarget) {
        if (Test-Path -LiteralPath $facFailed) {
            throw "Cannot quarantine the failed target because $facFailed already exists"
        }
        New-Item -ItemType Directory -Path $facFailedParent -Force | Out-Null
        Move-Item -LiteralPath $facTarget -Destination $facFailed
    }
    if ((Test-Path -LiteralPath $facRollback -PathType Container) -and
        -not (Test-Path -LiteralPath $facTarget)) {
        Move-Item -LiteralPath $facRollback -Destination $facTarget
    }
}

$facInstallerExitCode = $null
$facTargetMoved = $false
try {
    $facIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $facPrincipal = [Security.Principal.WindowsPrincipal]::new($facIdentity)
    if (-not $facPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'This operation must run elevated.'
    }

    if (([IO.Path]::GetFullPath($facLibraryRoot)).TrimEnd('\') -ne 'D:\Games\Factorio') {
        throw 'The library-root identity did not match the reviewed target.'
    }
    if (([IO.Path]::GetFullPath($facTarget)).TrimEnd('\') -ne 'D:\Games\Factorio\2.0') {
        throw 'The target identity did not match the reviewed target.'
    }
    if (-not (Test-Path -LiteralPath $facTarget -PathType Container)) {
        throw "The reviewed source target does not exist: $facTarget"
    }
    if (Test-Path -LiteralPath $facRollback) {
        throw "The rollback target already exists: $facRollback"
    }
    if (Test-Path -LiteralPath $facFailed) {
        throw "The failed-install quarantine target already exists: $facFailed"
    }
    if (-not (Test-Path -LiteralPath $facInstallerRoot -PathType Container)) {
        throw "The inspected installer directory does not exist: $facInstallerRoot"
    }
    if ((Get-Item -LiteralPath $facTarget -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'The exact target root is a reparse point.'
    }
    $facNestedReparse = Get-ChildItem -LiteralPath $facTarget -Force -Recurse |
        Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
        Select-Object -First 1
    if ($null -ne $facNestedReparse) {
        throw "The existing target contains a reparse point: $($facNestedReparse.FullName)"
    }
    if (Get-Process -Name factorio -ErrorAction SilentlyContinue) {
        throw 'Factorio is running. Close it before reinstalling the selected version.'
    }

    foreach ($facEntry in $facExpectedHashes.GetEnumerator()) {
        $facPath = Join-Path $facInstallerRoot $facEntry.Key
        if (-not (Test-Path -LiteralPath $facPath -PathType Leaf)) {
            throw "A required split-installer file is missing: $facPath"
        }
        $facActualHash = (Get-FileHash -LiteralPath $facPath -Algorithm SHA256).Hash
        if ($facActualHash -ne $facEntry.Value) {
            throw "Hash mismatch for $($facEntry.Key)"
        }
    }
    $facSignature = Get-AuthenticodeSignature -LiteralPath $facInstaller
    if ($facSignature.Status -ne 'Valid' -or
        $facSignature.SignerCertificate.Subject -notmatch 'CN=Wube Software Ltd') {
        throw 'The installer no longer has the reviewed valid Wube Software signature.'
    }

    $facRegistryBefore = Get-ItemProperty -LiteralPath $facRegistryPsPath
    if ($facRegistryBefore.InstallLocation.TrimEnd('\') -ne 'D:\Games\Factorio\2.1' -or
        $facRegistryBefore.UninstallString -notmatch 'D:\\Games\\Factorio\\2\.1\\unins000\.exe') {
        throw 'The shared Space Age uninstall key no longer identifies the reviewed 2.1 installation.'
    }

    New-Item -ItemType Directory -Path $facOperationRoot -Force | Out-Null
    & reg.exe export $facRegistryKey $facRegistrySnapshot /y | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $facRegistrySnapshot -PathType Leaf)) {
        throw "The exact 2.1 uninstall-key snapshot failed with reg.exe exit $LASTEXITCODE"
    }

    New-Item -ItemType Directory -Path $facRollbackParent -Force | Out-Null
    Move-Item -LiteralPath $facTarget -Destination $facRollback
    $facTargetMoved = $true

    $facInstallerArgs = @(
        '/SP-',
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        '/NOICONS',
        ('/DIR="' + $facTarget + '"'),
        ('/LOG="' + $facInstallerLog + '"')
    )
    $facInstallerProcess = Start-Process -FilePath $facInstaller -ArgumentList $facInstallerArgs -Wait -PassThru
    $facInstallerExitCode = $facInstallerProcess.ExitCode
    if ($facInstallerExitCode -ne 0) {
        throw "The Wube installer exited with code $facInstallerExitCode"
    }

    $facRequiredInstalledPaths = @(
        (Join-Path $facTarget 'bin\x64\factorio.exe'),
        (Join-Path $facTarget 'data'),
        (Join-Path $facTarget 'config-path.cfg'),
        (Join-Path $facTarget 'unins000.exe'),
        (Join-Path $facTarget 'unins000.dat')
    )
    foreach ($facRequiredPath in $facRequiredInstalledPaths) {
        if (-not (Test-Path -LiteralPath $facRequiredPath)) {
            throw "The official installation is incomplete: $facRequiredPath is missing"
        }
    }

    Restore-FacRegistry
    $facRegistryAfter = Get-ItemProperty -LiteralPath $facRegistryPsPath
    if ($facRegistryAfter.InstallLocation.TrimEnd('\') -ne 'D:\Games\Factorio\2.1' -or
        $facRegistryAfter.UninstallString -notmatch 'D:\\Games\\Factorio\\2\.1\\unins000\.exe') {
        throw 'The restored uninstall key does not identify 2.1.'
    }

    Write-FacResult -Status 'success' -Detail 'Official 2.0.77 installed; original portable tree retained; exact 2.1 uninstall key restored.' -InstallerExitCode $facInstallerExitCode
    exit 0
}
catch {
    $facFailure = $_.Exception.Message
    try {
        if ($facTargetMoved) {
            Restore-FacTarget
        }
        Restore-FacRegistry
    }
    catch {
        $facFailure = "$facFailure Rollback error: $($_.Exception.Message)"
    }
    if (-not (Test-Path -LiteralPath $facOperationRoot)) {
        New-Item -ItemType Directory -Path $facOperationRoot -Force | Out-Null
    }
    Write-FacResult -Status 'failed_rolled_back_or_recovery_required' -Detail $facFailure -InstallerExitCode $facInstallerExitCode
    Write-Error $facFailure
    exit 1
}
