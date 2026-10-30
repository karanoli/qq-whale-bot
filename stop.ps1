$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'task-common.ps1')
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'STOP'),'stop')
$task=Get-QQBotOwnedTask
if($task -and $task.State -eq 'Running'){
    Start-Sleep -Seconds 2
    $task=Get-QQBotOwnedTask
    if($task.State -eq 'Running'){Stop-ScheduledTask -TaskName $QQBotTaskName}
}
Write-Host '机器人已停止；QQ 和模型服务保持运行。'
