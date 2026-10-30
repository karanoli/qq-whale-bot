$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
$state=Join-Path $repo '.local-ai'
$settings=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $state 'services.local.json') | ConvertFrom-Json
$config=Join-Path $state 'chat.local.json'
if(Get-NetTCPConnection -State Listen -LocalPort $settings.chat_port -ErrorAction SilentlyContinue){throw '聊天端口已被占用，未停止原服务，也未重复启动。'}
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUNBUFFERED='1'
$arguments='-u "'+$settings.strata_server+'" --engine strata --config "'+$config+'" --host 127.0.0.1 --port '+$settings.chat_port
$process=Start-Process -FilePath $settings.strata_python -ArgumentList $arguments -WorkingDirectory $settings.strata_cwd -RedirectStandardOutput (Join-Path $state 'logs/chat-server.out.log') -RedirectStandardError (Join-Path $state 'logs/chat-server.err.log') -NoNewWindow -PassThru
$process.Id | Set-Content -LiteralPath (Join-Path $state 'chat.pid') -Encoding ASCII
Write-Host '聊天服务加载中；首次加载可能需要几分钟。日志在 .local-ai/logs。'
$process.WaitForExit()
exit $process.ExitCode
