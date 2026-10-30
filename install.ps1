param(
 [ValidateSet('Local','API')][string]$Mode='Local',
 [string]$AiRoot='D:\QQWhaleAI',
 [string]$Python='',
 [string]$QQName='',
 [string]$Endpoint='',
 [string]$Model='',
 [string]$ReuseModels='',
 [string]$HfEndpoint='',
 [switch]$Plan
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if($Plan){
 $lock=Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'deployment/models.lock.json')|ConvertFrom-Json
 [pscustomobject]@{Mode=$Mode;AiRoot=$AiRoot;Model=$lock.model.name;NativeVision=$true;WeightBytes=($lock.model.files|Measure-Object -Property size -Sum).Sum;Python='3.10-3.12';ManualSteps='登录官方QQ、设置昵称、添加监听对象'}|ConvertTo-Json
 return
}
if($env:OS -ne 'Windows_NT'){throw '安装用于Windows 10/11；Mac可整理源码和运行核心测试。'}
if($Mode -eq 'API' -and (!$Endpoint -or !$Model)){throw 'API模式请同时提供-Endpoint和-Model。'}
$launcher=$Python
if(!$launcher){
 foreach($v in @('3.12','3.11','3.10')){
  if(Get-Command py.exe -ErrorAction SilentlyContinue){
   $found=(& py.exe "-$v" -c "import sys;print(sys.executable)" 2>$null)
   if($LASTEXITCODE -eq 0 -and $found){$launcher=[string]($found|Select-Object -Last 1);break}
  }
 }
}
if(!$launcher -and (Get-Command python.exe -ErrorAction SilentlyContinue)){
 try{
  & python.exe -c "import sys,tkinter;assert (3,10)<=sys.version_info[:2]<(3,13)"
  if($LASTEXITCODE -eq 0){$launcher=(Get-Command python.exe).Source}
 }catch{}
}
if(!$launcher){
 # Official per-user Python installer; verify its signed publisher before executing it.
 $target=Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312'
 $candidate=Join-Path $target 'python.exe'
 if(Test-Path -LiteralPath $candidate){$launcher=$candidate}else{
  $bootstrap=Join-Path $PSScriptRoot '.local-ai/bootstrap'
  [void][IO.Directory]::CreateDirectory($bootstrap)
  $installer=Join-Path $bootstrap 'python-3.12.10-amd64.exe'
  [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
  Write-Host '正在获取Python官方安装程序……'
  Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer
  $signature=Get-AuthenticodeSignature -LiteralPath $installer
  if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation'){throw 'Python安装程序签名未通过；未执行。'}
  $arguments='/quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_launcher=0 Include_tcltk=1 Include_pip=1 TargetDir="'+$target+'"'
  $process=Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
  if($process.ExitCode -ne 0 -and $process.ExitCode -ne 3010){throw 'Python安装失败，请从python.org安装3.10-3.12后重试。'}
  if(!(Test-Path -LiteralPath $candidate)){throw 'Python安装完成但解释器未找到。'}
  Remove-Item -LiteralPath $installer
  $launcher=$candidate
 }
}
& (Join-Path $PSScriptRoot 'setup.ps1') -Python $launcher
$pythonExe=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$env:PYTHONIOENCODING='utf-8'
$configure=Join-Path $PSScriptRoot 'deployment/configure_bot.py'
$options=@()
if($QQName){$options+=@('--qq-name',$QQName)}
if($Mode -eq 'API'){$options+=@('--endpoint',$Endpoint,'--model',$Model,'--api-mode')}
& $pythonExe $configure @options
if($LASTEXITCODE -ne 0){throw '机器人配置失败。'}
if($Mode -eq 'Local'){
 $options=@('--ai-root',$AiRoot)
 if($ReuseModels){$options+=@('--reuse-models',$ReuseModels)}
 if($HfEndpoint){$options+=@('--hf-endpoint',$HfEndpoint)}
 & $pythonExe (Join-Path $PSScriptRoot 'deployment/install_local_ai.py') @options
 if($LASTEXITCODE -ne 0){throw '本地模型尚未装完；修复上方错误后重跑同一命令，下载可续传。'}
}
Write-Host '软件部署完成。请登录官方QQ，确认config.json内self_names是自己的QQ昵称。'
Write-Host '运行manage.cmd添加并核验群聊/个人，然后用start-all.cmd启动；stop-all.cmd停止本项目自己的服务。'
