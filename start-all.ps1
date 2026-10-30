$ErrorActionPreference='Stop'
$settings=Join-Path $PSScriptRoot '.local-ai/services.local.json'
$cfg=Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'config.json')|ConvertFrom-Json
if(Test-Path -LiteralPath $settings){
 $service=Get-Content -Raw -Encoding UTF8 $settings|ConvertFrom-Json
 $localEndpoint='http://127.0.0.1:'+$service.chat_port+'/v1/chat/completions'
 if($cfg.endpoint -eq $localEndpoint){& (Join-Path $PSScriptRoot 'deployment/start-local-ai.ps1')}
}
& (Join-Path $PSScriptRoot 'start.ps1')
