param([long]$Handle,[string]$OutputPath,[string]$ExpectedId='')
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Handle)
$deadline=(Get-Date).AddSeconds(3);$names=@()
do {
 $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
 $names=@($all | ForEach-Object {if($_.Current.Name){$_.Current.Name};$v=$null;if($_.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$v)){$v.Current.Value}} | Where-Object {$_} | Select-Object -Unique)
 if(($ExpectedId -and $names -contains $ExpectedId) -or (-not $ExpectedId -and @($names|Where-Object {$_ -match '\d{5,12}'}).Count)){break}
 Start-Sleep -Milliseconds 200
}while((Get-Date) -lt $deadline)
[IO.File]::WriteAllText($OutputPath,(ConvertTo-Json -InputObject @($names)),(New-Object Text.UTF8Encoding $false))
