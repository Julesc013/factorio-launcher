[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$VMName = 'Windows 10'
$ExpectedVMId = [Guid]'3ebbe558-91b9-435b-96e4-0c8199bd38ad'
$RequiredSafetyCheckpoint = 'Pre-recovery locked state 20260811-230037'
$LogRoot = 'D:\Projects\Factorio\Evidence\HyperV-Proof\Recovery'
$LogPath = Join-Path $LogRoot ("vm-start-recovery-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
Start-Transcript -Path $LogPath -Force

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Recovery must run from an elevated administrator token.'
    }

    Import-Module Hyper-V -ErrorAction Stop
    $vm = Get-VM -Name $VMName -ErrorAction Stop
    if ($vm.Id -ne $ExpectedVMId) {
        throw "VM identity mismatch. Expected $ExpectedVMId, found $($vm.Id)."
    }

    $safety = @(Get-VMSnapshot -VM $vm -ErrorAction Stop |
        Where-Object Name -CEQ $RequiredSafetyCheckpoint)
    if ($safety.Count -ne 1) {
        throw "Expected exactly one safety checkpoint named '$RequiredSafetyCheckpoint'; found $($safety.Count)."
    }

    if ($vm.State -ne 'Off') {
        throw "Expected the verified VM to be Off before recovery start; found $($vm.State)."
    }

    Set-VM -VM $vm -CheckpointType Disabled -AutomaticCheckpointsEnabled $false -ErrorAction Stop
    $vm = Get-VM -Id $ExpectedVMId -ErrorAction Stop
    if ($vm.CheckpointType -ne [Microsoft.HyperV.PowerShell.CheckpointType]::Disabled -or $vm.AutomaticCheckpointsEnabled) {
        throw 'Failed to restore the intended checkpoint policy.'
    }

    $services = @(Get-VMIntegrationService -VM $vm -ErrorAction Stop)
    $guestService = @($services | Where-Object Name -CEQ 'Guest Service Interface')
    if ($guestService.Count -ne 1) {
        throw "Expected exactly one Hyper-V Guest Service Interface; found $($guestService.Count)."
    }
    if (-not $guestService[0].Enabled) {
        Enable-VMIntegrationService -VMIntegrationService $guestService[0] -ErrorAction Stop
    }

    $guestService = @(Get-VMIntegrationService -VM $vm -ErrorAction Stop |
        Where-Object Name -CEQ 'Guest Service Interface')[0]
    if (-not $guestService.Enabled) {
        throw 'Hyper-V Guest Service Interface did not become enabled.'
    }

    Start-VM -VM $vm -ErrorAction Stop | Out-Null
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 2
        $vm = Get-VM -Id $ExpectedVMId -ErrorAction Stop
        if ((Get-Date) -gt $deadline) {
            throw 'VM did not reach Running state.'
        }
    } while ($vm.State -ne 'Running')

    Write-Host "Verified VM: $VMName ($ExpectedVMId)" -ForegroundColor Green
    Write-Host "Safety checkpoint retained: $RequiredSafetyCheckpoint" -ForegroundColor Green
    Write-Host 'Checkpoint creation disabled; automatic checkpoints disabled.' -ForegroundColor Green
    Write-Host 'Hyper-V Guest Service Interface enabled.' -ForegroundColor Green
    Write-Host 'VM running; opening console.' -ForegroundColor Green
    Write-Host "Log: $LogPath" -ForegroundColor Green

    Start-Process -FilePath "$env:SystemRoot\System32\vmconnect.exe" -ArgumentList @('localhost', ('"{0}"' -f $VMName))
}
catch {
    Write-Error $_
    throw
}
finally {
    Stop-Transcript
}
