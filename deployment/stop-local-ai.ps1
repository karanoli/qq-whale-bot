$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
$arguments='-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $PSScriptRoot 'serve-chat.ps1')+'"'
$task=Get-ScheduledTask QQWhaleLocalAI -ErrorAction SilentlyContinue
if(!$task){return}
if(@($task.Actions).Count -ne 1 -or $task.Actions[0].Arguments -ne $arguments){throw '模型任务属于另一份仓库，未操作。'}
$state=Join-Path $repo '.local-ai'
$pidFile=Join-Path $state 'chat.pid'
if(Test-Path -LiteralPath $pidFile){
 $serverId=[int](Get-Content -LiteralPath $pidFile -First 1)
 $process=Get-CimInstance Win32_Process -Filter "ProcessId=$serverId" -ErrorAction SilentlyContinue
 $configPath=Join-Path $state 'chat.local.json'
 if($process -and $process.CommandLine.Contains($configPath)){& taskkill.exe /PID $serverId /T /F}
}
Stop-ScheduledTask QQWhaleLocalAI
Write-Host '本项目自己的本地模型已停止；其他模型服务未操作。'
