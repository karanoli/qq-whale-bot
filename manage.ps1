$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $pythonExe)){throw '请先运行 setup.cmd。'}
& $pythonExe (Join-Path $PSScriptRoot 'manager.py')
if($LASTEXITCODE -ne 0){throw '管理器退出异常，请查看终端错误。'}
