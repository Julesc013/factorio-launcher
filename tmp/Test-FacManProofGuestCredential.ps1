[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ExpectedVMId = [Guid]'3ebbe558-91b9-435b-96e4-0c8199bd38ad'
$CredentialPath = Join-Path $env:LOCALAPPDATA 'FacManProof\pr131-guest-credential.clixml'
$LogRoot = 'D:\Projects\Factorio\Evidence\HyperV-Proof\Recovery'
$LogPath = Join-Path $LogRoot ("guest-credential-qualified-test-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
Start-Transcript -Path $LogPath -Force

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Credential test must run from an elevated administrator token.'
    }

    Import-Module Hyper-V -ErrorAction Stop
    $vm = Get-VM -Id $ExpectedVMId -ErrorAction Stop
    if ($vm.Name -cne 'Windows 10' -or $vm.State -ne 'Running') {
        throw "Exact VM identity/state check failed: name=$($vm.Name), state=$($vm.State)."
    }

    $stored = Import-Clixml -LiteralPath $CredentialPath
    if ($stored.UserName -cne 'Jules') { throw 'Stored credential username is not Jules.' }
    $qualified = [Management.Automation.PSCredential]::new('.\Jules', $stored.Password)

    Write-Host 'Making one PowerShell Direct authentication attempt as .\Jules.' -ForegroundColor Cyan
    $session = New-PSSession -VMId $ExpectedVMId -Credential $qualified -ErrorAction Stop

    $result = Invoke-Command -Session $session -ScriptBlock {
        $statusPath = 'C:\Windows\Temp\FacManProofCredentialBootstrap.status'
        $bootstrapRoot = 'C:\ProgramData\FacManProofRecovery'
        $launcherPath = 'C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp\FacManProofCredentialBootstrap.cmd'
        $status = if (Test-Path -LiteralPath $statusPath) { (Get-Content -LiteralPath $statusPath -Raw).Trim() } else { 'MISSING' }
        $user = Get-LocalUser -Name 'Jules'
        $service = Get-Service -Name 'vmicguestinterface' -ErrorAction Stop
        $winlogon = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
        $autoLogon = (Get-ItemProperty -LiteralPath $winlogon -Name AutoAdminLogon -ErrorAction SilentlyContinue).AutoAdminLogon

        Remove-Item -LiteralPath $statusPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $launcherPath -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $bootstrapRoot) {
            $resolved = [IO.Path]::GetFullPath($bootstrapRoot).TrimEnd('\')
            if ($resolved -cne 'C:\ProgramData\FacManProofRecovery') { throw 'Bootstrap cleanup root mismatch.' }
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }

        [pscustomobject]@{
            computer = $env:COMPUTERNAME
            identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
            bootstrap_status = $status
            user_enabled = $user.Enabled
            guest_service_status = $service.Status.ToString()
            auto_logon = [string]$autoLogon
            proof_root_exists = Test-Path -LiteralPath 'C:\FSC'
        }
    }

    $result | Format-List
    if ($result.bootstrap_status -cne 'SUCCESS') { throw "Bootstrap status was '$($result.bootstrap_status)'." }
    if (-not $result.user_enabled) { throw 'Jules is not enabled.' }
    if ($result.auto_logon -cne '0') { throw "AutoAdminLogon is '$($result.auto_logon)', expected '0'." }
    if ($result.proof_root_exists) { throw 'C:\FSC unexpectedly exists.' }

    Write-Host 'Qualified guest credential test passed; bootstrap residue removed.' -ForegroundColor Green
    Write-Host "Log: $LogPath" -ForegroundColor Green
}
finally {
    if ($null -ne $session) { Remove-PSSession -Session $session -ErrorAction SilentlyContinue }
    Remove-Variable stored, qualified -ErrorAction SilentlyContinue
    [GC]::Collect()
    Stop-Transcript
}
