param([string]$Python='')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$launcher=$Python
$pyArgs=@()
if(-not $launcher){
    if(Get-Command py.exe -ErrorAction SilentlyContinue){
        foreach($version in @('3.12','3.11','3.10')){
            try {
                & py.exe "-$version" -c "import sys;sys.exit(0)" 2>$null
                if($LASTEXITCODE -eq 0){$launcher='py.exe';$pyArgs=@("-$version");break}
            } catch { continue }
        }
    }
    if(-not $launcher -and (Get-Command python.exe -ErrorAction SilentlyContinue)){$launcher='python.exe'}
}
if(-not $launcher){throw '请先安装 Python 3.10、3.11 或 3.12（含 tkinter 和 pip）。'}
& $launcher @pyArgs -c "import sys;assert (3,10)<=sys.version_info[:2]<(3,13),'Please use Python 3.10-3.12';assert sys.maxsize>2**32,'Please use 64-bit Python';import tkinter"
if($LASTEXITCODE -ne 0){throw 'Python 版本不合适或未安装 tkinter。可用 -Python 指定解释器路径。'}
$venv=Join-Path $PSScriptRoot '.venv'
$pythonExe=Join-Path $venv 'Scripts\python.exe'
if(-not (Test-Path -LiteralPath $pythonExe)){
    & $launcher @pyArgs -m venv $venv
    if($LASTEXITCODE -ne 0){throw '创建虚拟环境失败。'}
}
& $pythonExe -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if($LASTEXITCODE -ne 0){throw '依赖安装失败，请检查上方错误后重试。'}
foreach($pair in @(@('config.example.json','config.json'),@('targets.example.json','targets.json'),@('personality.example.md','personality.md'))){
    $destination=Join-Path $PSScriptRoot $pair[1]
    if(-not (Test-Path -LiteralPath $destination)){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $pair[0]) -Destination $destination}
}
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'diagnostics') | Out-Null
Write-Host '安装完成。先修改 config.json 的模型接口、模型名和自己的 QQ 昵称，再运行 manage.cmd。'
Write-Host '模型服务需要单独启动；本脚本不下载模型、不修改 QQ。'
