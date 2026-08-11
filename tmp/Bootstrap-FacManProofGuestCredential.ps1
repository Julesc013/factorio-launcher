[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$VMName = 'Windows 10'
$ExpectedVMId = [Guid]'3ebbe558-91b9-435b-96e4-0c8199bd38ad'
$GuestUser = 'Jules'
$CredentialRoot = Join-Path $env:LOCALAPPDATA 'FacManProof'
$CredentialPath = Join-Path $CredentialRoot 'pr131-guest-credential.clixml'
$LogRoot = 'D:\Projects\Factorio\Evidence\HyperV-Proof\Recovery'
$LogPath = Join-Path $LogRoot ("guest-credential-bootstrap-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$GuestRecoveryRoot = 'C:\ProgramData\FacManProofRecovery'
$GuestBootstrapPath = Join-Path $GuestRecoveryRoot 'Bootstrap.ps1'
$GuestLauncherPath = 'C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp\FacManProofCredentialBootstrap.cmd'
$GuestStatusPath = 'C:\Windows\Temp\FacManProofCredentialBootstrap.status'
$nonce = [Guid]::NewGuid().ToString('N')
$HostBootstrapPath = Join-Path $env:TEMP ("facman-proof-bootstrap-$nonce.ps1")
$HostLauncherPath = Join-Path $env:TEMP ("facman-proof-launcher-$nonce.cmd")

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
Start-Transcript -Path $LogPath -Force

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Credential bootstrap must run from an elevated administrator token.'
    }

    Import-Module Hyper-V -ErrorAction Stop
    $vm = Get-VM -Name $VMName -ErrorAction Stop
    if ($vm.Id -ne $ExpectedVMId) {
        throw "VM identity mismatch. Expected $ExpectedVMId, found $($vm.Id)."
    }
    if ($vm.State -ne 'Running') {
        throw "Expected the exact VM to be Running; found $($vm.State)."
    }

    $guestService = @(Get-VMIntegrationService -VM $vm -ErrorAction Stop |
        Where-Object Name -CEQ 'Guest Service Interface')
    if ($guestService.Count -ne 1 -or -not $guestService[0].Enabled) {
        throw 'Hyper-V Guest Service Interface is not enabled on the exact VM.'
    }

    $plainPassword = [Guid]::NewGuid().ToString('N') + 'aA1!'
    $passwordBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($plainPassword))
    $securePassword = ConvertTo-SecureString $plainPassword -AsPlainText -Force
    $credential = [Management.Automation.PSCredential]::new($GuestUser, $securePassword)

    New-Item -ItemType Directory -Path $CredentialRoot -Force | Out-Null
    & icacls.exe $CredentialRoot /inheritance:r /grant:r "$($identity.Name):(OI)(CI)F" 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Failed to restrict the host credential directory ACL.' }
    $credential | Export-Clixml -LiteralPath $CredentialPath -Force

    $guestScriptTemplate = @'
$ErrorActionPreference = 'Stop'
$statusPath = 'C:\Windows\Temp\FacManProofCredentialBootstrap.status'
$launcherPath = 'C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp\FacManProofCredentialBootstrap.cmd'
try {
    $plain = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__PASSWORD_BASE64__'))
    $secure = ConvertTo-SecureString $plain -AsPlainText -Force
    Unlock-LocalUser -Name 'Jules' -ErrorAction SilentlyContinue
    Enable-LocalUser -Name 'Jules' -ErrorAction SilentlyContinue
    Set-LocalUser -Name 'Jules' -Password $secure -ErrorAction Stop

    $winlogon = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
    Set-ItemProperty -LiteralPath $winlogon -Name AutoAdminLogon -Value '0' -Type String
    Remove-ItemProperty -LiteralPath $winlogon -Name DefaultPassword -ErrorAction SilentlyContinue

    Set-Content -LiteralPath $statusPath -Value 'SUCCESS' -Encoding Ascii -Force
    Remove-Variable plain, secure -ErrorAction SilentlyContinue
}
catch {
    Set-Content -LiteralPath $statusPath -Value ('FAILED: ' + $_.Exception.Message) -Encoding UTF8 -Force
}
finally {
    Remove-Item -LiteralPath $launcherPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
}
'@
    $guestScript = $guestScriptTemplate.Replace('__PASSWORD_BASE64__', $passwordBase64)
    [IO.File]::WriteAllText($HostBootstrapPath, $guestScript, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText(
        $HostLauncherPath,
        "@echo off`r`npowershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$GuestBootstrapPath`"`r`n",
        [Text.ASCIIEncoding]::new()
    )

    Write-Host 'Copying self-deleting credential bootstrap through Hyper-V Guest Service Interface.' -ForegroundColor Cyan
    Copy-VMFile -VM $vm -SourcePath $HostBootstrapPath -DestinationPath $GuestBootstrapPath -FileSource Host -CreateFullPath -Force -ErrorAction Stop
    Copy-VMFile -VM $vm -SourcePath $HostLauncherPath -DestinationPath $GuestLauncherPath -FileSource Host -CreateFullPath -Force -ErrorAction Stop

    Write-Host 'Restarting the guest once so the local-console startup payload can run.' -ForegroundColor Cyan
    Stop-VM -VM $vm -ErrorAction Stop
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 2
        $vm = Get-VM -Id $ExpectedVMId -ErrorAction Stop
        if ((Get-Date) -gt $deadline) { throw 'Guest did not shut down gracefully.' }
    } while ($vm.State -ne 'Off')

    Start-VM -VM $vm -ErrorAction Stop | Out-Null
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 2
        $vm = Get-VM -Id $ExpectedVMId -ErrorAction Stop
        if ((Get-Date) -gt $deadline) { throw 'Guest did not reach Running state.' }
    } while ($vm.State -ne 'Running')

    Write-Host 'Waiting for Windows startup and the one-time payload; no authentication attempts are made during this interval.' -ForegroundColor Cyan
    Start-Sleep -Seconds 75

    $session = $null
    try {
        $session = New-PSSession -VMId $ExpectedVMId -Credential $credential -ErrorAction Stop
    }
    catch {
        throw 'The single post-bootstrap PowerShell Direct authentication attempt failed. No retries were made.'
    }

    $guestResult = Invoke-Command -Session $session -ScriptBlock {
        $statusPath = 'C:\Windows\Temp\FacManProofCredentialBootstrap.status'
        $status = if (Test-Path -LiteralPath $statusPath) { Get-Content -LiteralPath $statusPath -Raw } else { 'MISSING' }
        $user = Get-LocalUser -Name 'Jules'
        $service = Get-Service -Name 'vmicguestinterface' -ErrorAction Stop
        Remove-Item -LiteralPath $statusPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath 'C:\ProgramData\FacManProofRecovery' -Force -ErrorAction SilentlyContinue
        [pscustomobject]@{
            status = $status.Trim()
            user = $user.Name
            user_enabled = $user.Enabled
            guest_service = $service.Name
            guest_service_status = $service.Status.ToString()
            proof_root_exists = Test-Path -LiteralPath 'C:\FSC'
        }
    }
    if ($guestResult.status -cne 'SUCCESS') {
        throw "Guest bootstrap did not report success: $($guestResult.status)"
    }
    if (-not $guestResult.user_enabled) { throw 'Guest Jules account is not enabled.' }
    if ($guestResult.proof_root_exists) { throw 'Guest proof root C:\FSC unexpectedly exists after credential bootstrap.' }

    Write-Host 'Secure guest credential bootstrap passed.' -ForegroundColor Green
    Write-Host "Guest user: $($guestResult.user), enabled=$($guestResult.user_enabled)" -ForegroundColor Green
    Write-Host "Guest service: $($guestResult.guest_service), status=$($guestResult.guest_service_status)" -ForegroundColor Green
    Write-Host "Guest proof root exists: $($guestResult.proof_root_exists)" -ForegroundColor Green
    Write-Host "DPAPI credential: $CredentialPath" -ForegroundColor Green
    Write-Host "Log: $LogPath" -ForegroundColor Green
}
finally {
    if ($null -ne $session) { Remove-PSSession -Session $session -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $HostBootstrapPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $HostLauncherPath -Force -ErrorAction SilentlyContinue
    Remove-Variable plainPassword, passwordBase64, securePassword, credential, guestScript -ErrorAction SilentlyContinue
    [GC]::Collect()
    Stop-Transcript
}
