param([string]$Contact='', [string]$OutputPath='')
$ErrorActionPreference='Stop'
[void][IO.Directory]::CreateDirectory((Join-Path $PSScriptRoot 'diagnostics'))
if(-not $OutputPath){$OutputPath=Join-Path $PSScriptRoot 'diagnostics/direct-read/messages.json'}
[void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($OutputPath)))
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class QQNativeClick {
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr p);
}
'@
[void][QQNativeClick]::SetProcessDPIAware()

$qq=@(Get-Process QQ | Select-Object -ExpandProperty Id)
$wins=[System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
$window=@($wins|Where-Object {$qq -contains $_.Current.ProcessId -and $_.Current.Name -eq 'QQ'})
if($window.Count -ne 1){throw 'Expected exactly one QQ window'}
$w=$window[0]
$RequestedContact=$Contact
function Header-Matches($header){
 if(-not $RequestedContact){return $true}
 $want=($RequestedContact -replace '\s','').Normalize([System.Text.NormalizationForm]::FormKC);$got=($header -replace '\s','').Normalize([System.Text.NormalizationForm]::FormKC)
 return ($want -eq $got -or ($want.Length -ge 7 -and $got.StartsWith($want.Substring(0,7))))
}
if($Contact){
 $initial=$w.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
 $active=@($initial|Where-Object {$_.Current.ClassName -match '(^|\s)chat-header__contact-name(\s|$)'})
 if($active.Count -eq 1 -and (Header-Matches $active[0].Current.Name)){$Contact=''}
}
if($Contact){
 $want=($Contact -replace '\s','').Normalize([System.Text.NormalizationForm]::FormKC);$deadline=(Get-Date).AddSeconds(6);$found=@()
 do {
  $found=@();$all=$w.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
  foreach($e in $all){
   $n=($e.Current.Name -replace '\s','').Normalize([System.Text.NormalizationForm]::FormKC)
   if($n -ne $want -and -not ($want.Length -ge 7 -and $n.StartsWith($want.Substring(0,7)))){continue}
   $parent=$e
   for($i=0;$i -lt 4 -and $parent;$i++){
    if($parent.Current.ClassName -match '(^|\s)recent-contact-item(\s|$)'){$found+=,$parent;break}
    $parent=[System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($parent)
   }
  }
  $found=@($found | Group-Object -Property { $_.GetRuntimeId() -join ',' } | ForEach-Object { $_.Group[0] })
  if($found.Count -eq 1){break}
  Start-Sleep -Milliseconds 250
 } while((Get-Date) -lt $deadline)
 if($found.Count -ne 1){
  $debug=@{want=$want;nodes=$all.Count;items=@($all|ForEach-Object {@{name=$_.Current.Name;class=$_.Current.ClassName;type=$_.Current.ControlType.ProgrammaticName}})}
  [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'diagnostics/lookup-failure.json'),(ConvertTo-Json $debug -Depth 5),(New-Object Text.UTF8Encoding $false))
  throw ('Recent contact absent or ambiguous; unique matches='+$found.Count+'; nothing opened')}
 $rect=$found[0].Current.BoundingRectangle
 if($rect.Width -lt 10 -or $rect.Height -lt 10 -or [QQNativeClick]::GetForegroundWindow().ToInt64() -ne $w.Current.NativeWindowHandle){throw 'QQ focus or contact bounds changed; no click performed'}
 $invoke=$found[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
 $invoke.Invoke()
 Start-Sleep -Milliseconds 700

}
$all=$w.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$header=@($all|Where-Object {$_.Current.ClassName -match '(^|\s)chat-header__contact-name(\s|$)'})
$headerDeadline=(Get-Date).AddSeconds(5)
while(($header.Count -ne 1 -or -not (Header-Matches $header[0].Current.Name)) -and (Get-Date) -lt $headerDeadline){
 Start-Sleep -Milliseconds 200
 $all=$w.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
 $header=@($all|Where-Object {$_.Current.ClassName -match '(^|\s)chat-header__contact-name(\s|$)'})
}
if($header.Count -ne 1 -or -not (Header-Matches $header[0].Current.Name)){
 $diag=@{requested=$RequestedContact;clickRect=@($rect.X,$rect.Y,$rect.Width,$rect.Height);actual=@($header|ForEach-Object {$_.Current.Name});nodes=$all.Count}
 [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'diagnostics/switch-title-failure.json'),(ConvertTo-Json $diag -Depth 4),(New-Object Text.UTF8Encoding $false))
 throw 'Requested chat did not become active; nothing read'
}
$messages=@()
foreach($e in $all){if($e.Current.ClassName -notmatch '(^|\s)message(\s|$)'){continue}
 $children=$e.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
 $parts=@();$own=$false
 foreach($c in $children){
  if($c.Current.ClassName -match 'container--self'){$own=$true}
  $parts+=@{name=$c.Current.Name;class=$c.Current.ClassName;type=$c.Current.ControlType.ProgrammaticName;id=$c.Current.AutomationId;help=$c.Current.HelpText}
 }
 $text=@($children|Where-Object {$_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text -and $_.Current.Name.Trim()}|ForEach-Object {$_.Current.Name})
 $contents=@($children|Where-Object {$_.Current.ClassName -match '^msg-content-container'})
 $body=@();$imageCount=0
 if($contents.Count -eq 1){
  $items=$contents[0].FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
  $body=@($items|Where-Object {$_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text -and $_.Current.Name.Trim()}|ForEach-Object {$_.Current.Name})
  $imageCount=@($items|Where-Object {$_.Current.ClassName -match 'pic-element'}).Count
 }
 $avatars=@($children|Where-Object {$_.Current.ClassName -eq 'avatar-span' -and $_.Current.Name})
 $sender=if($avatars.Count){$avatars[0].Current.Name}else{''}
 $bounds=@();if($imageCount -gt 0){foreach($pic in @($items|Where-Object {$_.Current.ClassName -match 'pic-element'})){$bounds+=@{runtime_id=($pic.GetRuntimeId() -join ',')}}}
 $messages+=@{image_bounds=$bounds;self=$own;parts=$parts;text=$text;body=($body -join [Environment]::NewLine);image_count=$imageCount;sender=$sender;display_time=''}
}
$result=@{header=$header[0].Current.Name;method='Windows UI Automation';time=(Get-Date).ToString('o');messages=$messages;clipboardUsed=$false;selectionUsed=$false;scope='Currently loaded UI messages only; not a full database feed'}
[IO.File]::WriteAllText($OutputPath,(ConvertTo-Json $result -Depth 8),(New-Object Text.UTF8Encoding $false))