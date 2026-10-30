$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
$state=Join-Path $repo '.local-ai'
$settings=Get-Content -Raw -Encoding UTF8 (Join-Path $state 'services.local.json')|ConvertFrom-Json
$config=Get-Content -Raw -Encoding UTF8 (Join-Path $state 'chat.local.json')|ConvertFrom-Json
$port=$settings.chat_port
try{
 $models=Invoke-RestMethod ("http://127.0.0.1:"+$port+"/v1/models") -TimeoutSec 3
 if(@($models.data|Where-Object {$_.id -eq $config.model_name -and $_.architecture.input_modalities -contains 'image'}).Count){
  Write-Host '原生模型服务已可用，复用现有服务。';return
 }
}catch{}
if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw '模型端口被其他服务占用；未停止它。'}
$name='QQWhaleLocalAI'
$arguments='-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $PSScriptRoot 'serve-chat.ps1')+'"'
$task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if($task){
 if(@($task.Actions).Count -ne 1 -or $task.Actions[0].Arguments -ne $arguments){throw 'QQWhaleLocalAI属于另一份仓库，未操作。'}
}else{
 $action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $repo
 $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
 $options=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
 Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $options|Out-Null
}
if((Get-ScheduledTask $name).State -ne 'Running'){Start-ScheduledTask $name}
Write-Host '正在等待原生模型加载……'
for($i=0;$i -lt 180;$i++){
 Start-Sleep 2
 try{
  $models=Invoke-RestMethod ("http://127.0.0.1:"+$port+"/v1/models") -TimeoutSec 3
  if(@($models.data|Where-Object {$_.id -eq $config.model_name -and $_.architecture.input_modalities -contains 'image'}).Count){return}
 }catch{}
}
throw '模型未就绪；查看.local-ai/logs。加载任务继续运行。'
