$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'stop.ps1')
& (Join-Path $PSScriptRoot 'deployment/stop-local-ai.ps1')
