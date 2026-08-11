$ErrorActionPreference = 'Stop'
$test = 'D:\Projects\Factorio\factorio-launcher\.codex-tmp\Test-FacManProofGuestCredential.ps1'
Start-Process `
    -FilePath 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' `
    -Verb RunAs `
    -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $test))
