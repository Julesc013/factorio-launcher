# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
param([Parameter(Mandatory=$true)][long]$Handle,
      [Parameter(Mandatory=$true)][int]$ExpectedPid)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$source = @'
using System;
using System.Runtime.CompilerServices;
using System.Windows.Automation;
public static class FacmanOwnedInvoke {
 [MethodImpl(MethodImplOptions.NoInlining)]
 public static void Initialize() {
  ClientSettings.RegisterClientSideProviders(new ClientSideProviderDescription[0]);
 }
 public static string Invoke(long handle, int pid) {
  var element = AutomationElement.FromHandle(new IntPtr(handle));
  var current = element.Current;
  if(current.ProcessId != pid || current.NativeWindowHandle != handle ||
     current.ControlType != ControlType.Button || !current.IsEnabled)
   throw new InvalidOperationException("Accessibility button identity differs");
  var name = current.Name;
  var pattern = (InvokePattern)element.GetCurrentPattern(InvokePattern.Pattern);
  pattern.Invoke();
  return name;
 }
}
'@
Add-Type -TypeDefinition $source -ReferencedAssemblies @('System.dll',
 [Windows.Automation.AutomationElement].Assembly.Location,
 [Windows.Automation.ControlType].Assembly.Location)
if([Threading.Thread]::CurrentThread.ApartmentState -ne 'MTA'){throw 'UIA client requires MTA'}
[FacmanOwnedInvoke]::Initialize()
$name = [FacmanOwnedInvoke]::Invoke($Handle, $ExpectedPid)
@{pid=$ExpectedPid;hwnd=$Handle;accessible_name=$name;invoked=$true} | ConvertTo-Json -Compress
