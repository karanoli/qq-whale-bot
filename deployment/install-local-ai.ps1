param([string]$AiRoot='D:\QQWhaleAI',[string]$ReuseModels='',[string]$HfEndpoint='',[switch]$Plan)
$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
$python=Join-Path $repo '.venv/Scripts/python.exe'
if(!(Test-Path -LiteralPath $python)){throw '先在根目录运行install.ps1或setup.cmd。'}
$options=@('--ai-root',$AiRoot)
if($ReuseModels){$options+=@('--reuse-models',$ReuseModels)}
if($HfEndpoint){$options+=@('--hf-endpoint',$HfEndpoint)}
if($Plan){$options+='--plan'}
& $python (Join-Path $PSScriptRoot 'install_local_ai.py') @options
if($LASTEXITCODE -ne 0){throw '本地模型安装未完成，保留已下载数据供续传。'}
