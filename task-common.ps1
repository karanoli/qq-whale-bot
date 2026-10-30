$ErrorActionPreference='Stop'
$QQBotTaskName='QQWhaleBot'
$QQBotPython=Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$QQBotArguments='"'+(Join-Path $PSScriptRoot 'bot.py')+'" --run'
function Get-QQBotOwnedTask {
    $task=Get-ScheduledTask -TaskName $QQBotTaskName -ErrorAction SilentlyContinue
    if($task){
        $actions=@($task.Actions)
        if($actions.Count -ne 1 -or $actions[0].Execute -ne $QQBotPython -or $actions[0].Arguments -ne $QQBotArguments){
            throw 'QQWhaleBot 任务属于另一份项目，未操作。请先确认安装位置。'
        }
    }
    return $task
}
