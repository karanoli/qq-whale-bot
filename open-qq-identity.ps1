param([long]$Handle,[string]$ExpectedContact,[string]$OutputPath)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$w=[System.Windows.Automation.AutomationElement]::FromHandle([intptr]$Handle)
$all=$w.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$header=@($all|Where-Object {$_.Current.ClassName -match '(^|\s)chat-header__contact-name(\s|$)'})
if($header.Count -ne 1){throw 'Expected exactly one chat header'}
$name=$header[0].Current.Name
$want=($ExpectedContact -replace '\s','').Normalize([System.Text.NormalizationForm]::FormKC)
$got=($name -replace '\s','').Normalize([System.Text.NormalizationForm]::FormKC)
if($want -ne $got -and -not ($want.Length -ge 7 -and $got.StartsWith($want.Substring(0,7)))){throw 'Chat changed before opening identity card'}
$invoke=$header[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
$invoke.Invoke()
[IO.File]::WriteAllText($OutputPath,(ConvertTo-Json @{header=$name;method='UIA InvokePattern';time=(Get-Date).ToString('o')}),(New-Object Text.UTF8Encoding $false))
