$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'task-common.ps1')
Set-Location -LiteralPath $PSScriptRoot
if(-not (Test-Path -LiteralPath $QQBotPython)){throw '请先运行 setup.cmd。'}
$task=Get-QQBotOwnedTask
if($task -and $task.State -eq 'Running'){Write-Host '小鲸已经在运行。';exit 0}
if(-not (Get-Process QQ -ErrorAction SilentlyContinue)){throw '请先打开并登录官方 Windows QQ。'}
$pythonExe=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $pythonExe (Join-Path $PSScriptRoot 'doctor.py') --services-only
if($LASTEXITCODE -ne 0){throw '模型配置检查未通过，请先启动模型服务并修改 config.json。'}
$targets=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'targets.json') | ConvertFrom-Json
if(-not @($targets.targets | Where-Object {$_.enabled -ne $false}).Count){throw '还没有启用的监听对象，请先运行 manage.cmd。'}
if(-not $task){
    $action=New-ScheduledTaskAction -Execute $QQBotPython -Argument $QQBotArguments -WorkingDirectory $PSScriptRoot
    $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $QQBotTaskName -Action $action -Principal $principal -Settings $settings | Out-Null
}
Remove-Item -LiteralPath (Join-Path $PSScriptRoot 'STOP') -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $QQBotTaskName
Write-Host '小鲸已启动。保持 QQ 可见，勿锁屏。按 F8 或运行 stop.cmd 停止。'
